"""Clearly synthetic source artifacts, confined to the marked V4 checks database."""
import csv
import hashlib
import io
import json
from pathlib import Path

from psycopg.types.json import Jsonb
from shared.db.importer import canonical_bytes, source_uuid, read_ledger, write_ledger
from module3_interactions.engine import BoundedDataset

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("DDInter900001", "DDInter900002", "DDInter900003")
NAMES = ("Synthetic Alpha", "Synthetic Beta", "Synthetic Gamma")


def fixture_sources(repo):
    folder = ROOT / "artifacts/core_db_v4/fixtures"
    folder.mkdir(parents=True, exist_ok=True)
    records = {
        "medications": [{"id": f"TEST_P{n}", "name": f"Core Fixture {n}"} for n in range(4)],
        "ingredients": [{"id": f"TEST_I{n}", "name": f"Source Label {n}"} for n in range(4)],
        "medication_ingredients": [{"id": f"TEST_C{n}", "medication_id": f"TEST_P{n}"} for n in range(4)],
        "ddinter_mappings": [{"id": f"TEST_M{n}", "component_id": f"TEST_C{c}", "target_id": TARGETS[t]}
                            for n, (c, t) in enumerate(((0, 0), (1, 1), (2, 1), (2, 2)))]}
    hashes = {}
    for name, rows in records.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        data = stream.getvalue().encode()
        hashes[name] = hashlib.sha256(data).hexdigest()
        (folder / (name + ".csv")).write_bytes(data)
    manifest = {"schema": "synthetic-core-test-build.v4", "synthetic": True, "files": hashes}
    raw = canonical_bytes(manifest)
    build = hashlib.sha256(raw).hexdigest()
    artifact = folder / (build + ".json")
    artifact.write_bytes(raw)

    def source(name, row, attrs=None):
        result = {"schema": "csv-source.v4", "csv": name + ".csv", "artifact_sha256": hashes[name],
                  "source_id": row["id"], "source_record_id": None, "rule_version": "synthetic-test-fixture.v4",
                  "source_ref": {"id": row["id"], "relation": "explicit_synthetic_fixture",
                                 "record_sha256": hashlib.sha256(canonical_bytes(row)).hexdigest()},
                  "manifest_locator": {"uri": artifact.as_uri(), "artifact_sha256": build}}
        if attrs is not None:
            result["source_attributes"] = attrs
        return result

    uid = lambda name, key: source_uuid(build, name, key)
    products = [uid("medications", f"TEST_P{n}") for n in range(4)]
    if repo._one("SELECT msa.published(%s) AS yes", (build,))["yes"]:
        return build, products
    with repo.db.transaction():
        repo.db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,4))", (build,))
        ledger = read_ledger(repo.db)
        ledger["builds"][build] = {"synthetic": True, "published": False, "manifest_sha256": build,
                                  "manifest_uri": artifact.as_uri(), "files": hashes}
        write_ledger(repo.db, ledger)
        for n, row in enumerate(records["ingredients"]):
            repo._insert("msa_ref.ingredients", id=uid("ingredients", row["id"]), source_ingredient_id=row["id"],
                         dataset_build=build, name_original=row["name"], name_normalized=row["name"],
                         acceptance_scope="EXPLICIT_SYNTHETIC_TEST_LABEL", source_locator=source("ingredients", row))
        for n, row in enumerate(records["medications"]):
            details = {k: None for k in ("registration_token", "registration_number_source", "packaging",
                       "release_characteristic", "route_status", "release_status", "dosage_form_status")}
            details.update(schema="product-details.v4", source_identity_definition={"strength": "500mg"})
            repo._insert("msa_ref.medications", id=products[n], source_medication_id=row["id"], dataset_build=build,
                         brand_name=row["name"], component_count=1, product_details=details,
                         source_locator=source("medications", row))
        for n, row in enumerate(records["medication_ingredients"]):
            repo._insert("msa_ref.medication_ingredients", id=uid("medication_ingredients", row["id"]),
                         medication_id=products[n], ingredient_id=uid("ingredients", f"TEST_I{n}") if n < 3 else None,
                         dataset_build=build, source_component_id=row["id"], ordinal=1,
                         ingredient_name_raw=f"Source Label {n}", ingredient_text_raw=f"Synthetic component {n} 500 mg",
                         strength_basis={"schema": "strength-basis.v4", "expression_raw": "500 mg",
                                         "primary_strength_assertion_id": None, "strength_source_status": None,
                                         "strength_transform_status": None, "strength_basis_verified": False,
                                         "numeric_assertions": []}, source_locator=source("medication_ingredients", row))
        for row in records["ddinter_mappings"]:
            c = int(row["component_id"][-1])
            t = TARGETS.index(row["target_id"])
            repo._insert("msa_ref.ddinter_mappings", id=uid("ddinter_mappings", row["id"]),
                         source_mapping_id=row["id"], component_id=uid("medication_ingredients", row["component_id"]),
                         dataset_build=build, target_id=row["target_id"], mapping_set_id=f"TEST_SET{c}",
                         target_catalog_sha256=hashes["ddinter_mappings"], retrieval_evidence=[],
                         source_locator=source("ddinter_mappings", row, {"component_id": row["component_id"],
                             "medication_id": f"TEST_P{c}", "source_name": NAMES[t]}))
        repo.db.execute("SELECT msa.assert_ref_build(%s)", (build,))
        ledger["builds"][build]["published"] = True
        write_ledger(repo.db, ledger)
    return build, products


def dataset(*, fail_on_call=None, conflict=False, subset=False):
    rows = [{"DDInterID_A": TARGETS[a], "Drug_A": NAMES[a], "DDInterID_B": TARGETS[b], "Drug_B": NAMES[b], "Level": "Major"}
            for a, b in ((0, 1), (0, 2), (1, 2))]
    if subset:
        rows = rows[:1]
    if conflict:
        rows.append(dict(rows[0], Level="Minor"))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    raw = stream.getvalue().encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = ROOT / f"artifacts/core_db_v4/fixtures/interactions-{digest}.csv"
    path.write_bytes(raw)
    value = BoundedDataset(rows, {"loaded_rows": len(rows), "csv_sha256": digest,
                                 "source_url": path.as_uri(), "synthetic_fixture": True,
                                 "scope": "Explicit synthetic test source; never patient data"}, row_limit=len(rows))
    if fail_on_call:
        original = value.lookup
        calls = [0]
        def failing(a, b):
            calls[0] += 1
            if calls[0] == fail_on_call:
                raise RuntimeError("Explicit synthetic interrupted lookup")
            return original(a, b)
        value.lookup = failing
    return value
