"""Idempotent projection of all six expert-approved CSV files. No review gates."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from psycopg import sql
from psycopg.types.json import Jsonb

COUNTS = dict(medications=10670, ingredients=1940, medication_ingredients=12899,
              ddinter_mappings=5675, medication_indications=5614, medication_priorities=6105)
PROJECTION_VERSION = "core-db-v4.1"
HASH_CONTRACT = "pg-jsonb-text-v4"
ROOT = Path(__file__).resolve().parents[3]


def canonical_bytes(value):
    """Manifest bytes only. Application JSON digests always use msa.digest in PostgreSQL."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_sources(directory):
    data, hashes = {}, {}
    for name, expected in COUNTS.items():
        path = Path(directory) / (name + ".csv")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        # Projection integrity and reconciliation, not another expert eligibility review.
        if len(rows) != expected or len({r["id"] for r in rows}) != expected:
            raise ValueError("Unexpected source count or duplicate source ID: " + name)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError("Malformed CSV width: " + name)
        data[name] = rows
    return data, hashes


def source_uuid(build, table, source_id):
    return uuid5(NAMESPACE_URL, f"msa/core/v4/{build}/{table}/{source_id}")


def read_ledger(db):
    row = db.execute("SELECT obj_description('msa_ref'::regnamespace,'pg_namespace')").fetchone()
    return json.loads(row[0]) if row and row[0] else {"schema": "ref-build-ledger.v4", "builds": {}}


def write_ledger(db, ledger):
    db.execute(sql.SQL("COMMENT ON SCHEMA msa_ref IS {}").format(sql.Literal(json.dumps(ledger, sort_keys=True))))


def reconcile(db, build, sources=None):
    counts, ids = {}, {}
    source_columns = dict(medications="source_medication_id", ingredients="source_ingredient_id",
                          medication_ingredients="source_component_id", ddinter_mappings="source_mapping_id")
    for name, key in source_columns.items():
        rows = db.execute(sql.SQL("SELECT {} FROM msa_ref.{} WHERE dataset_build=%s").format(
            sql.Identifier(key), sql.Identifier(name)), (build,)).fetchall()
        ids[name] = {r[0] for r in rows}
        counts[name] = len(rows)
    for name, column in (("medication_indications", "indications"), ("medication_priorities", "priorities")):
        rows = db.execute(sql.SQL(
            "SELECT e->>'id' FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.{}) e WHERE dataset_build=%s"
        ).format(sql.Identifier(column)), (build,)).fetchall()
        ids[name] = {r[0] for r in rows}
        counts[name] = len(rows)
    if sources is not None:
        for name in COUNTS:
            if ids[name] != {r["id"] for r in sources[name]} or counts[name] != COUNTS[name]:
                raise ValueError("Source-ID reconciliation failed: " + name)
    return {"counts": counts, "relational_ref_rows": sum(counts[n] for n in source_columns),
            "jsonb_records": counts["medication_indications"] + counts["medication_priorities"],
            "total_source_records": sum(counts.values()), "source_id_sets_match": sources is not None}


def import_datasets(db, directory, *, manifest_directory=None):
    sources, hashes = read_sources(directory)
    manifest = {"schema": "core-ref-build.v4", "projection_version": PROJECTION_VERSION,
                "namespace": "medication-safety-expert-approved", "synthetic": False,
                "hash_contract": HASH_CONTRACT,
                "files": {n: {"sha256": hashes[n], "records": COUNTS[n]} for n in sorted(COUNTS)},
                "approval": {"basis": "User confirmed expert approval of all six datasets and DDInter mappings",
                             "scope": "All retained source records; historical review flags are provenance only"}}
    raw = canonical_bytes(manifest)
    build = hashlib.sha256(raw).hexdigest()
    folder = Path(manifest_directory or ROOT / "artifacts/core_db_v4/manifests")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (build + ".json")
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("Immutable manifest artifact changed")
    if not path.exists():
        with path.open("xb") as stream:
            stream.write(raw)
    manifest_locator = {"uri": f"artifact://core-db-v4/manifests/{build}.json",
                        "artifact_sha256": build, "object_version": None}
    uid = lambda name, key: source_uuid(build, name, key)

    def source(name, row, *, attributes=None, legacy=()):
        value = {"schema": "csv-source.v4", "csv": name + ".csv", "artifact_sha256": hashes[name],
                 "source_id": row["id"], "source_record_id": row.get("source_record_id") or None,
                 "source_ref": json.loads(row["source_ref"]), "rule_version": row.get("rule_version") or None,
                 "manifest_locator": manifest_locator}
        if "record_version" in row:
            value["record_version"] = row["record_version"] or None
        if attributes is not None:
            value["source_attributes"] = attributes
        if legacy:
            value["legacy_review"] = {k: row[k] for k in legacy if k in row}
        return value

    def nullable(row, *keys):
        return {k: row.get(k) or None for k in keys}

    grouped = {n: defaultdict(list) for n in ("medication_indications", "medication_priorities")}
    meds = {r["id"]: r for r in sources["medications"]}
    ings = {r["id"]: r for r in sources["ingredients"]}
    comps = {r["id"]: r for r in sources["medication_ingredients"]}
    for name, groups in grouped.items():
        for row in sources[name]:
            if row["medication_id"] not in meds:
                raise ValueError("Related row has no medication parent: " + row["id"])
            if name == "medication_indications":
                value = {k: row[k] for k in ("id", "medication_id", "assertion_kind", "polarity", "text_raw", "expression_state")}
                value.update({k: json.loads(row[k]) for k in ("condition_expression", "source_qualifications", "literal_operators")})
                legacy = ("status", "approval_status", "approved_product_indication", "transformation_status")
            else:
                value = {k: row[k] for k in ("id", "medication_id", "purpose", "collection_priority_tier", "source_clinical_priority", "policy_status")}
                value.update({k: json.loads(row[k]) for k in ("condition_groups", "selected_condition_groups")})
                for key in ("selected_for_hdsd_collection", "clinical_recommendation"):
                    if row[key] not in ("true", "false"):
                        raise ValueError("Missing source boolean, cannot invent it: " + row["id"])
                    value[key] = row[key] == "true"
                legacy = ("transformation_status",)
            value["source_locator"] = source(name, row, legacy=legacy)
            groups[row["medication_id"]].append(value)

    with db.transaction():
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,4))", (build,))
        ledger = read_ledger(db)
        if ledger["builds"].get(build, {}).get("published"):
            result = reconcile(db, build, sources)
            return dict(result, dataset_build=build, reused_build=True, files_sha256=hashes,
                        manifest=str(path.resolve()), hash_contract=HASH_CONTRACT)
        entry = {"published": False, "synthetic": False, "manifest_sha256": build,
                 "manifest_uri": manifest_locator["uri"], "files": hashes, "projection_version": PROJECTION_VERSION}
        ledger["builds"][build] = entry
        write_ledger(db, ledger)

        def copy(table, columns, values):
            with db.cursor().copy(sql.SQL("COPY msa_ref.{} ({}) FROM STDIN").format(
                    sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)))) as writer:
                for value in values:
                    writer.write_row(value)

        values = []
        for r in sources["ingredients"]:
            attrs = nullable(r, "local_normalized_name", "accepted_normalized_name", "accepted_normalized_identity_id", "identity_kind", "international_mapping_required")
            loc = source("ingredients", r, attributes=attrs,
                         legacy=("identity_status", "clinical_identity_verified", "unresolved_reason", "transformation_status"))
            values.append((uid("ingredients", r["id"]), r["id"], build, r["source_name"],
                           r["accepted_normalized_name"] or r["local_normalized_name"] or None,
                           r["acceptance_scope"], Jsonb(loc)))
        copy("ingredients", ["id", "source_ingredient_id", "dataset_build", "name_original", "name_normalized", "acceptance_scope", "source_locator"], values)

        values = []
        for r in sources["medications"]:
            details = dict(schema="product-details.v4", **nullable(r, "registration_token", "registration_number_source", "packaging", "release_characteristic", "route_status", "release_status", "dosage_form_status"),
                           source_identity_definition=json.loads(r["identity_definition"]))
            loc = source("medications", r, legacy=("identity_state", "integration_state", "composition_state",
                         "complete_active_composition_verified", "level2_qualified", "retained_review_flags", "transformation_status"))
            values.append((uid("medications", r["id"]), r["id"], build, r["brand_name"], r["manufacturer"] or None,
                           r["dosage_form"] or None, r["route"] or None, int(r["component_count"]) if r["component_count"] else None,
                           Jsonb(details), Jsonb(grouped["medication_indications"][r["id"]]),
                           Jsonb(grouped["medication_priorities"][r["id"]]), Jsonb(loc)))
        copy("medications", ["id", "source_medication_id", "dataset_build", "brand_name", "manufacturer", "dosage_form", "route", "component_count", "product_details", "indications", "priorities", "source_locator"], values)

        values = []
        for r in sources["medication_ingredients"]:
            attrs = nullable(r, "ingredient_id", "accepted_ingredient_id", "parse_id", "original_field", "chemical_form_id")
            attrs.update({k: json.loads(r[k]) if r[k] else None for k in ("original_span", "physical_descriptors")})
            loc = source("medication_ingredients", r, attributes=attrs,
                         legacy=("identity_state", "identity_verified", "issues", "transformation_status"))
            local_id = r["accepted_ingredient_id"] or r["ingredient_id"]
            basis = dict(schema="strength-basis.v4", expression_raw=r["ingredient_text_raw"] or None,
                         numeric_assertions=[], **nullable(r, "primary_strength_assertion_id", "strength_source_status", "strength_transform_status"),
                         strength_basis_verified=r["strength_basis_verified"])
            values.append((uid("medication_ingredients", r["id"]), uid("medications", r["medication_id"]),
                           uid("ingredients", local_id) if local_id in ings else None, build, r["id"], int(r["ordinal"]),
                           r["original_name_candidate"] or None, r["ingredient_text_raw"], r["chemical_form_raw"] or None,
                           r["equivalence_declaration_raw"] or None, Jsonb(basis), Jsonb(loc)))
        copy("medication_ingredients", ["id", "medication_id", "ingredient_id", "dataset_build", "source_component_id", "ordinal",
             "ingredient_name_raw", "ingredient_text_raw", "chemical_form_raw", "equivalence_raw", "strength_basis", "source_locator"], values)

        values = []
        for r in sources["ddinter_mappings"]:
            if r["component_id"] not in comps or comps[r["component_id"]]["medication_id"] != r["medication_id"]:
                raise ValueError("Mapping source parent is missing/mismatched: " + r["id"])
            loc = source("ddinter_mappings", r, attributes=nullable(r, "component_id", "medication_id", "source_name"),
                         legacy=("status", "accepted", "operative", "unresolved_reason", "transformation_status"))
            values.append((uid("ddinter_mappings", r["id"]), r["id"], uid("medication_ingredients", r["component_id"]), build,
                           r["candidate_target_identifier"] or None, r["mapping_set_id"] or None,
                           r["candidate_catalog_sha256"] or None, Jsonb(json.loads(r["retrieval_evidence"])), Jsonb(loc)))
        copy("ddinter_mappings", ["id", "source_mapping_id", "component_id", "dataset_build", "target_id", "mapping_set_id",
             "target_catalog_sha256", "retrieval_evidence", "source_locator"], values)
        db.execute("SELECT msa.assert_ref_build(%s)", (build,))
        result = reconcile(db, build, sources)
        entry["published"] = True
        ledger["builds"][build] = entry
        write_ledger(db, ledger)
    return dict(result, dataset_build=build, reused_build=False, files_sha256=hashes,
                manifest=str(path.resolve()), hash_contract=HASH_CONTRACT)
