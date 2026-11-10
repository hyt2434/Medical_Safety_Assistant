"""Behavior and approved-contract checks on real PostgreSQL, never DB mocks."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import unittest
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from psycopg import sql

from fixtures import fixture_sources, dataset, TARGETS
from manage import migrate
from shared.db import CoreRepository
from shared.db.importer import import_datasets, read_sources, reconcile, read_ledger, write_ledger
from shared.db.intake_adapter import persist_module1, medication_fields
from shared.db.identification_adapter import run_identification
from shared.db.safety_adapter import run_safety, finding_evidence

ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("CORE_DB_DSN")


class CoreV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN:
            raise RuntimeError("Real PostgreSQL V4 checks DSN required")
        cls.db = psycopg.connect(DSN, autocommit=True)
        marker = cls.db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if not re.fullmatch(r"msa_core_test_v4[a-z0-9]+", cls.db.info.dbname) or marker != "Medication Safety Assistant Core V4 isolated test":
            raise RuntimeError("Refusing tests on unmarked/shared database")
        if not cls.db.info.dbname.endswith("checks"):
            raise RuntimeError("Synthetic fixtures require a dedicated ...checks database")
        cls.sources, _ = read_sources(ROOT / "data/datasets")
        cls.imported = import_datasets(cls.db, ROOT / "data/datasets")
        cls.build = cls.imported["dataset_build"]
        bootstrap_owner = uuid4()
        cls.db.execute("INSERT INTO identity.users(id) VALUES (%s)", (bootstrap_owner,))
        cls.fixture_build, cls.products = fixture_sources(CoreRepository(cls.db, authenticated_owner=bootstrap_owner))

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.owner, self.other = uuid4(), uuid4()
        self.db.execute("INSERT INTO identity.users(id) VALUES (%s),(%s)", (self.owner, self.other))
        self.repo = CoreRepository(self.db, authenticated_owner=self.owner)
        self.foreign = CoreRepository(self.db, authenticated_owner=self.other)
        self.chat = self.repo.create_conversation()
        self.intake = self.repo.create_intake(self.chat["id"])

    def entry(self, n=0, *, confirm=True, repo=None, intake=None):
        repo = repo or self.repo
        intake = intake or self.intake["id"]
        fields = medication_fields({"name_raw": f"Core Fixture {n}", "strength_raw": "500 mg",
                                    "evidence_text": f"Explicit synthetic fixture {n}"})
        raw = fields["name_raw"].encode()
        inp = repo.record_input(intake, "MANUAL", raw,
                                payload={"schema": "input.v4", "digest_basis": "ORIGINAL_BYTES", "text": raw.decode()})
        x = repo.record_extraction(inp["id"], "MANUAL_PASS_THROUGH", "synthetic-fixture-v4",
                                   {"schema": "extraction.v4", "medications": [fields], "warnings": [], "document_instructions_raw": []})
        v = repo.create_item(x["id"], 1, fields)
        if confirm:
            return repo.confirm_entry(v["id"], v["content_digest"], uuid4(), explicit_confirmation=True)
        return v

    def snapshot(self, *numbers, context="SYNTHETIC_TEST"):
        entries = []
        for n in numbers:
            v = self.entry(n)
            match, _ = run_identification(self.repo, v["id"], dataset_build=self.fixture_build)
            self.assertEqual(match["match_status"], "SELECTED")
            entries.append((v["id"], match["id"]))
        return self.repo.create_snapshot(entries, data_context=context), entries

    def health_source(self):
        msg = self.repo.append_message(self.chat["id"], "USER", "Synthetic patient reports allergy status unknown")
        return self.repo.record_health_source(
            {"schema": "health-source.v4", "facts": [{"field": "allergies", "value": None,
             "text_raw": "allergy status unknown", "uncertainty": "UNKNOWN"}], "limitations": ["Synthetic test input"]}, message=msg["id"])

    def summary(self, *, supersedes=None, snapshot=None, assessment=None):
        source = self.health_source()
        refs = [self.repo.manifest_source("HEALTH_SOURCE", source["id"], "health")]
        if snapshot:
            refs.append(self.repo.manifest_source("SNAPSHOT", snapshot, "medications"))
        if assessment:
            refs.append(self.repo.manifest_source("ASSESSMENT", assessment, "assessment"))
        manifest = {"schema": "summary-manifest.v4", "sources": refs}
        content = {"schema": "patient-summary.v4", "as_of": "2026-11-08", "patient_context": {},
                   "conditions": {"state": "UNKNOWN", "items": []}, "allergies": {"state": "UNKNOWN", "items": []},
                   "medications": [], "safety_findings": [], "limitations": ["Synthetic fixture, not clinical advice"],
                   "sections": [{"key": "health", "title": "Health", "text": "Allergy status unknown", "source_keys": ["health"]}]}
        generation = {"schema": "summary-generation.v4", "generator_version": "synthetic-test-v4",
                      "template_version": "synthetic-summary-v4", "model_ref": None, "limitations": []}
        workflow = self.repo.create_workflow(self.chat["id"], "PATIENT_SUMMARY")
        pending = self.repo.prepare_summary(workflow["id"], content, manifest, generation, expected_revision=1)
        digest = pending["context"]["pending_confirmation"]["payload_digest"]
        request = uuid4()
        saved = self.repo.confirm_summary(workflow["id"], digest, pending["revision"], request,
                                         explicit_confirmation=True, supersedes=supersedes, snapshot=snapshot, assessment=assessment)
        return saved, pending, request, digest

    def test_01_exact_twenty_tables_193_attributes_types_and_nulls(self):
        contract = json.loads((ROOT / "db/schema_contract.json").read_text(encoding="utf-8"))
        tables = self.db.execute("""SELECT table_schema||'.'||table_name FROM information_schema.tables
            WHERE table_schema IN ('msa','msa_ref') AND table_type='BASE TABLE'""").fetchall()
        self.assertEqual({r[0] for r in tables}, {t["name"] for t in contract["tables"]})
        total = 0
        types = {"integer": "int4", "bigint": "int8"}
        for table in contract["tables"]:
            actual = self.db.execute("""SELECT a.attname,t.typname,a.attnotnull,a.attgenerated,
                pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
                LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""", (table["name"],)).fetchall()
            self.assertEqual([r[0] for r in actual], [c["name"] for c in table["columns"]])
            for row, expected in zip(actual, table["columns"]):
                self.assertEqual(row[1], types.get(expected["type"], expected["type"]))
                self.assertEqual(row[2], not expected["nullable"])
                if expected["default"] == "GENERATED ALWAYS":
                    self.assertEqual(row[3], "s")
                elif expected["default"] == "—":
                    self.assertIsNone(row[4])
                else:
                    self.assertIsNotNone(row[4])
            total += len(actual)
        self.assertEqual(total, 193)

    def test_02_forty_composite_foreign_keys_restrict_and_two_join_pks(self):
        rules = self.db.execute("""SELECT confupdtype,confdeltype FROM pg_constraint
            WHERE contype='f' AND connamespace IN ('msa'::regnamespace,'msa_ref'::regnamespace)""").fetchall()
        self.assertEqual(len(rules), 40)
        self.assertTrue(all(r == ("r", "r") for r in rules))
        for table, keys in (("snapshot_entries", "{snapshot_id,entry_version_id}"),
                            ("finding_entries", "{finding_id,entry_version_id}")):
            row = self.db.execute("""SELECT array_agg(a.attname ORDER BY k.n)::text FROM pg_constraint c
                CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum,n)
                JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
                WHERE c.contype='p' AND c.conrelid=%s::regclass""", ("msa." + table,)).fetchone()[0]
            self.assertEqual(row, keys)

    def test_03_all_six_source_id_sets_and_reconciliation(self):
        result = reconcile(self.db, self.build, self.sources)
        self.assertEqual((result["relational_ref_rows"], result["jsonb_records"], result["total_source_records"]), (31184, 11719, 42903))

    def test_04_idempotent_import_preserves_ids(self):
        result = import_datasets(self.db, ROOT / "data/datasets")
        self.assertTrue(result["reused_build"])
        self.assertEqual(result["dataset_build"], self.build)
        self.assertTrue(result["source_id_sets_match"])

    def test_05_source_hashes_unchanged_and_review_flags_not_gates(self):
        _, hashes = read_sources(ROOT / "data/datasets")
        self.assertEqual(hashes, self.imported["files_sha256"])
        count = self.db.execute("""SELECT count(*) FROM msa_ref.ddinter_mappings WHERE dataset_build=%s
            AND source_locator->'legacy_review'->>'accepted'='false'""", (self.build,)).fetchone()[0]
        self.assertEqual(count, 5675)

    def test_06_names_and_registration_release_preserved_without_sql_columns(self):
        med = self.db.execute("SELECT product_details FROM msa_ref.medications WHERE dataset_build=%s AND source_medication_id=%s",
                              (self.build, self.sources["medications"][0]["id"])).fetchone()[0]
        self.assertEqual(med["registration_token"], self.sources["medications"][0]["registration_token"] or None)
        self.assertIn("release_characteristic", med)
        mapping = self.db.execute("SELECT source_locator FROM msa_ref.ddinter_mappings WHERE dataset_build=%s AND source_mapping_id=%s",
                                  (self.build, self.sources["ddinter_mappings"][0]["id"])).fetchone()[0]
        self.assertEqual(mapping["source_attributes"]["source_name"], self.sources["ddinter_mappings"][0]["source_name"])

    def test_07_module1_adapter_all_modalities_and_exact_confirmation(self):
        for mode in ("MANUAL", "TEXT", "IMAGE", "AUDIO"):
            payload = {"schema": "input.v4", "digest_basis": "ORIGINAL_BYTES", "text": "Core Fixture 0"}
            if mode in ("IMAGE", "AUDIO"):
                payload["object_locator"] = {"uri": "fixture://explicit-retained-test-input", "object_version": "synthetic-v4"}
            saved = persist_module1(self.repo, self.intake["id"], b"synthetic retained bytes",
                {"medications": [{"name_raw": "Core Fixture 0", "strength_raw": "500mg"}]},
                modality=mode, input_payload=payload, extractor_name="explicit-synthetic-test",
                extractor_version="v4", content_type="application/octet-stream")
            self.assertIsNone(saved["entries"][0]["confirmed_at"])
            v = saved["entries"][0]
            confirmed = self.repo.confirm_entry(v["id"], v["content_digest"], uuid4(), explicit_confirmation=True)
            self.assertEqual(confirmed["id"], v["id"])

    def test_08_confirmation_rejects_stale_digest_and_non_explicit_action(self):
        v = self.entry(confirm=False)
        with self.assertRaises(ValueError):
            self.repo.confirm_entry(v["id"], v["content_digest"], uuid4(), explicit_confirmation=False)
        with self.assertRaises(psycopg.Error):
            self.repo.confirm_entry(v["id"], "f" * 64, uuid4(), explicit_confirmation=True)

    def test_09_owner_isolation_and_confirmation_request_reuse(self):
        v = self.entry(confirm=False)
        with self.assertRaises(PermissionError):
            self.foreign.confirm_entry(v["id"], v["content_digest"], uuid4(), explicit_confirmation=True)
        key = uuid4()
        a = self.repo.confirm_entry(v["id"], v["content_digest"], key, explicit_confirmation=True)
        b = self.repo.confirm_entry(v["id"], v["content_digest"], key, explicit_confirmation=True)
        self.assertEqual(a["id"], b["id"])
        other = self.entry(confirm=False)
        with self.assertRaises(ValueError):
            self.repo.confirm_entry(other["id"], other["content_digest"], key, explicit_confirmation=True)

    def test_10_corrections_have_consecutive_history_and_fresh_confirmation(self):
        old = self.entry()
        changed = self.repo.correct_entry(old["id"], medication_fields({"name_raw": "Core Fixture 1"}))
        self.assertEqual(changed["version_no"], old["version_no"] + 1)
        self.assertIsNone(changed["confirmed_at"])
        with self.assertRaises(psycopg.Error):
            self.repo.correct_entry(old["id"], old["medication_fields"])

    def test_11_confirmed_content_immutable(self):
        v = self.entry()
        with self.assertRaises(psycopg.Error):
            with self.repo.transaction():
                self.db.execute("UPDATE msa.medication_entry_versions SET medication_fields=jsonb_set(medication_fields,'{name_raw}','\"changed\"') WHERE id=%s", (v["id"],))

    def test_12_core_identification_selected_no_match_and_confidence_null(self):
        v = self.entry()
        match, _ = run_identification(self.repo, v["id"], dataset_build=self.fixture_build)
        self.assertEqual(match["product_id"], self.products[0])
        self.assertIsNone(match["confidence"])
        unknown = self.repo.correct_entry(v["id"], medication_fields({"name_raw": "No such source product"}))
        unknown = self.repo.confirm_entry(unknown["id"], unknown["content_digest"], uuid4(), explicit_confirmation=True)
        missed, _ = run_identification(self.repo, unknown["id"], dataset_build=self.fixture_build)
        self.assertEqual(missed["match_status"], "NO_MATCH")

    def test_13_external_module2_handles_need_crosswalk(self):
        class External:
            def lookup(self, fields):
                return {"identification_status": "VERIFIED", "candidates": [{"candidate_key": "test-only-external-handle"}]}
        v = self.entry()
        pending, _ = run_identification(self.repo, v["id"], reference=External())
        self.assertEqual(pending["match_status"], "AMBIGUOUS")
        chosen, _ = run_identification(self.repo, v["id"], reference=External(),
                                       accepted_source_crosswalk={"test-only-external-handle": self.products[0]})
        self.assertEqual(chosen["product_id"], self.products[0])

    def test_14_unconfirmed_input_cannot_enter_module2_or_snapshot(self):
        v = self.entry(confirm=False)
        with self.assertRaises(ValueError):
            run_identification(self.repo, v["id"], dataset_build=self.fixture_build)
        with self.assertRaises(psycopg.Error):
            self.repo.create_snapshot([(v["id"], None)], data_context="SYNTHETIC_TEST")

    def test_15_composite_product_build_fk_rejects_cross_build(self):
        v = self.entry()
        real = self.db.execute("SELECT id FROM msa_ref.medications WHERE dataset_build=%s LIMIT 1", (self.build,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.repo.record_match(v["id"], "SELECTED", product=real, reference_build=self.fixture_build)

    def test_16_match_attempt_requires_outcome_at_commit(self):
        v = self.entry()
        basis = {"schema": "match-evidence.v4", "method": "test", "qualifiers": {},
                 "external_candidates": [], "candidate_evidence": [], "outcome_reason": None, "limitations": []}
        with self.assertRaises(psycopg.Error):
            with self.repo.transaction():
                self.repo._insert("msa.entry_matches", user_id=self.owner, entry_version_id=v["id"], attempt_no=1,
                    match_status="CANDIDATE", candidate_rank=1, product_id=self.products[0],
                    reference_build=self.fixture_build, matcher_version="test", match_evidence=basis)

    def test_17_snapshot_references_all_multiple_targets(self):
        snap, _ = self.snapshot(2)
        row = self.repo.snapshot_context(snap["id"])[0]
        refs = row["component_context"]["mapping_refs"]
        self.assertEqual(len(refs), 2)
        targets = self.db.execute("SELECT target_id FROM msa_ref.ddinter_mappings WHERE id=ANY(%s::uuid[])",
                                  ([r["mapping_id"] for r in refs],)).fetchall()
        self.assertEqual({r[0] for r in targets}, set(TARGETS[1:]))

    def test_18_snapshot_hash_recomputes_and_is_immutable(self):
        snap, _ = self.snapshot(0, 1)
        actual = self.db.execute("SELECT msa.digest(msa.snapshot_document(%s))", (snap["id"],)).fetchone()[0]
        self.assertEqual(actual, snap["snapshot_digest"])
        with self.assertRaises(psycopg.Error):
            with self.repo.transaction():
                self.db.execute("UPDATE msa.medication_list_snapshots SET context_key='tampered' WHERE id=%s", (snap["id"],))

    def test_19_snapshot_one_version_per_item_and_no_cross_owner(self):
        v = self.entry()
        changed = self.repo.correct_entry(v["id"], v["medication_fields"])
        changed = self.repo.confirm_entry(changed["id"], changed["content_digest"], uuid4(), explicit_confirmation=True)
        with self.assertRaises(psycopg.Error):
            self.repo.create_snapshot([(v["id"], None), (changed["id"], None)], data_context="SYNTHETIC_TEST")
        with self.assertRaises(PermissionError):
            self.foreign.create_snapshot([(v["id"], None)])

    def test_20_synthetic_reference_blocked_in_patient_snapshot(self):
        with self.assertRaises(psycopg.Error):
            self.snapshot(0, context="PATIENT")

    def test_21_complete_pipeline_positive_finding_and_limited_coverage(self):
        snap, _ = self.snapshot(0, 1)
        saved, output = run_safety(self.repo, snap["id"], dataset())
        self.assertEqual(saved["execution_status"], "COMPLETED")
        self.assertEqual(saved["check_results"]["ddi"]["coverage"], "PARTIAL")
        self.assertIsNone(output["safe_to_take"])
        self.assertTrue(self.repo.severe_warnings())

    def test_22_multiple_targets_evaluated_without_pick_first(self):
        snap, _ = self.snapshot(0, 2)
        saved, output = run_safety(self.repo, snap["id"], dataset())
        findings = self.repo._all("SELECT evidence FROM msa.safety_findings WHERE assessment_id=%s AND finding_type='DDI'", (saved["id"],))
        pairs = {tuple(sorted(s["target_ids"])) for f in findings for s in f["evidence"]["sources"]}
        self.assertEqual(pairs, {tuple(sorted((TARGETS[0], TARGETS[1]))), tuple(sorted((TARGETS[0], TARGETS[2])))})
        self.assertEqual(saved["check_results"]["ddi"]["coverage"], "PARTIAL")

    def test_23_unresolved_mapping_preserved_in_pairs(self):
        snap, _ = self.snapshot(0, 3)
        saved, _ = run_safety(self.repo, snap["id"], dataset())
        self.assertEqual(saved["check_results"]["ddi"]["coverage"], "UNASSESSED")
        self.assertEqual(len(saved["check_results"]["ddi"]["pair_results"]), 1)
        self.assertEqual(len(self.repo.snapshot_context(snap["id"])), 2)

    def test_24_loaded_catalog_missing_target_gives_partial_not_fake_identity(self):
        snap, _ = self.snapshot(0, 2)
        saved, _ = run_safety(self.repo, snap["id"], dataset(subset=True))
        self.assertEqual(saved["check_results"]["ddi"]["coverage"], "PARTIAL")
        self.assertIn("MAPPING_TARGET_MISSING_OR_OUTSIDE_LOADED_IDENTITY_SCOPE", saved["check_results"]["ddi"]["limitations"])

    def test_25_duplicate_ingredient_separate_from_ddi_self_pair(self):
        snap, _ = self.snapshot(1, 1)
        saved, _ = run_safety(self.repo, snap["id"], dataset())
        kinds = self.repo._all("SELECT finding_type FROM msa.safety_findings WHERE assessment_id=%s", (saved["id"],))
        self.assertIn("DUPLICATE_INGREDIENT", {r["finding_type"] for r in kinds})
        self.assertNotIn("DDI", {r["finding_type"] for r in kinds})

    def test_26_single_occurrence_pairwise_not_applicable(self):
        snap, _ = self.snapshot(0)
        saved, _ = run_safety(self.repo, snap["id"], dataset())
        self.assertEqual(self.db.execute("SELECT msa.coverage(check_results) FROM msa.safety_assessments WHERE id=%s", (saved["id"],)).fetchone()[0], "NOT_APPLICABLE")

    def test_27_committed_major_warning_survives_later_lookup_error(self):
        snap, _ = self.snapshot(0, 1, 2)
        saved, _ = run_safety(self.repo, snap["id"], dataset(fail_on_call=2))
        self.assertEqual(saved["execution_status"], "FAILED")
        self.assertEqual(saved["check_results"]["ddi"]["coverage"], "PARTIAL")
        self.assertTrue(self.repo.severe_warnings())
        self.assertIsNotNone(saved["result_digest"])

    def test_28_retry_and_request_idempotency_do_not_erase_prior_findings(self):
        snap, _ = self.snapshot(0, 1)
        key = uuid4()
        first, _ = run_safety(self.repo, snap["id"], dataset(), request_key=key)
        again, _ = run_safety(self.repo, snap["id"], dataset(), request_key=key)
        self.assertEqual(first["id"], again["id"])
        retry, _ = run_safety(self.repo, snap["id"], dataset(), retry_of=first["id"])
        self.assertNotEqual(first["id"], retry["id"])
        self.assertEqual(retry["retry_of_assessment_id"], first["id"])
        self.assertGreaterEqual(len(self.repo.severe_warnings()), 2)

    def test_29_source_conflict_retains_all_levels(self):
        snap, _ = self.snapshot(0, 1)
        saved, _ = run_safety(self.repo, snap["id"], dataset(conflict=True))
        findings = self.repo._all("SELECT * FROM msa.safety_findings WHERE assessment_id=%s AND finding_type='SOURCE_CONFLICT'", (saved["id"],))
        self.assertEqual({s["source_severity"] for s in findings[0]["evidence"]["sources"]}, {"Major", "Minor"})
        self.assertEqual(saved["check_results"]["ddi"]["coverage"], "PARTIAL")

    def test_30_finding_cardinality_and_membership_are_transactional(self):
        snap, _ = self.snapshot(0, 1)
        attempt = self.repo.start_assessment(snap["id"], {"ddinter": {}, "engine_config": {}, "limitations": []})
        with self.assertRaises(psycopg.Error):
            self.repo.record_finding(attempt["id"], "invalid", "DDI", "MAJOR", "Invalid without evidence/members", finding_evidence("test"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM msa.safety_findings WHERE assessment_id=%s", (attempt["id"],)).fetchone()[0], 0)

    def test_31_cross_snapshot_finding_member_rejected(self):
        a, _ = self.snapshot(0)
        _, other = self.snapshot(1)
        attempt = self.repo.start_assessment(a["id"], {"ddinter": {}, "engine_config": {}, "limitations": []})
        with self.assertRaises(psycopg.Error):
            self.repo.record_finding(attempt["id"], "cross", "UNRESOLVED", "UNKNOWN", "Wrong membership", finding_evidence("test"), [other[0][0]])

    def test_32_json_missing_keys_and_forged_mapping_references_rejected(self):
        v = self.entry()
        with self.assertRaises(psycopg.Error):
            self.repo.record_input(self.intake["id"], "TEXT", b"x", payload={"schema": "input.v4", "digest_basis": "ORIGINAL_BYTES"})
        snap, entries = self.snapshot(0)
        context = deepcopy(self.repo.snapshot_context(snap["id"])[0]["component_context"])
        context["mapping_refs"][0]["mapping_id"] = str(uuid4())
        with self.assertRaises(psycopg.Error):
            with self.repo.transaction():
                draft = self.repo._insert("msa.medication_list_snapshots", user_id=self.owner, context_key="test", data_context="SYNTHETIC_TEST", as_of_at=snap["as_of_at"])
                self.repo._insert("msa.snapshot_entries", snapshot_id=draft["id"], entry_version_id=entries[0][0],
                                  user_id=self.owner, entry_match_id=entries[0][1], component_context=context)

    def test_33_owner_context_is_required_for_direct_patient_writes(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.execute("INSERT INTO msa.conversation_sessions(user_id) VALUES (%s)", (self.owner,))

    def test_34_summary_exact_confirmation_history_idempotency(self):
        first, pending, key, digest = self.summary()
        again = self.repo.confirm_summary(first["workflow_id"], digest, pending["revision"], key, explicit_confirmation=True)
        self.assertEqual(first["id"], again["id"])
        second, _, _, _ = self.summary(supersedes=first["id"])
        self.assertEqual(second["series_root_id"], first["id"])
        self.assertEqual(second["version_no"], 2)
        self.assertEqual(len(self.repo.summary_history(first["id"])), 2)

    def test_35_summary_cross_owner_source_and_stale_manifest_rejected(self):
        source = self.health_source()
        ref = self.repo.manifest_source("HEALTH_SOURCE", source["id"], "health")
        manifest = {"schema": "summary-manifest.v4", "sources": [ref]}
        with self.assertRaises(psycopg.Error):
            self.db.execute("SELECT msa.validate_manifest(%s,%s)", (Jsonb(manifest), self.other))
        ref["digest"] = "0" * 64
        with self.assertRaises(psycopg.Error):
            self.db.execute("SELECT msa.validate_manifest(%s,%s)", (Jsonb(manifest), self.owner))

    def test_36_summary_snapshot_assessment_pin_and_immutability(self):
        snap, _ = self.snapshot(0, 1)
        assessment, _ = run_safety(self.repo, snap["id"], dataset())
        saved, _, _, _ = self.summary(snapshot=snap["id"], assessment=assessment["id"])
        self.assertEqual(saved["primary_assessment_id"], assessment["id"])
        with self.assertRaises(psycopg.Error):
            with self.repo.transaction():
                self.db.execute("UPDATE msa.patient_health_summaries SET summary_content=summary_content WHERE id=%s", (saved["id"],))

    def test_37_canonical_hash_stable_for_json_key_order_and_timezones(self):
        a = self.repo.digest({"b": [1, None], "a": "thuốc"})
        b = self.repo.digest({"a": "thuốc", "b": [1, None]})
        self.assertEqual(a, b)
        source = self.health_source()
        self.db.execute("SET TIME ZONE 'Asia/Saigon'")
        try:
            actual = self.db.execute("""SELECT msa.health_digest(origin,source_content,source_date,verification_status,source_locator)
                FROM msa.patient_health_sources WHERE id=%s""", (source["id"],)).fetchone()[0]
            self.assertEqual(actual, source["content_digest"])
        finally:
            self.db.execute("SET TIME ZONE 'UTC'")

    def test_38_published_reference_cannot_be_modified_or_appended(self):
        with self.assertRaises(psycopg.Error):
            self.db.execute("UPDATE msa_ref.ddinter_mappings SET target_id=target_id WHERE dataset_build=%s", (self.build,))
        with self.assertRaises(psycopg.Error):
            self.db.execute("""INSERT INTO msa_ref.ingredients(source_ingredient_id,dataset_build,name_original,acceptance_scope,source_locator)
                SELECT source_ingredient_id||'_new',dataset_build,name_original,acceptance_scope,source_locator
                FROM msa_ref.ingredients WHERE dataset_build=%s LIMIT 1""", (self.build,))

    def test_39_concurrent_confirmation_returns_one_record(self):
        v = self.entry(confirm=False)
        key = uuid4()
        def confirm(_):
            with psycopg.connect(DSN, autocommit=True) as db:
                repo = CoreRepository(db, authenticated_owner=self.owner)
                return repo.confirm_entry(v["id"], v["content_digest"], key, explicit_confirmation=True)["id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(confirm, range(2)))
        self.assertEqual(results, [v["id"], v["id"]])

    def test_40_outer_transactions_rejected_for_warning_durability(self):
        with self.db.transaction():
            with self.assertRaises(RuntimeError):
                self.repo.create_conversation()

    def test_41_migration_retry_preserves_history_and_applied_checksums(self):
        entry = self.entry()
        result = migrate(self.db)
        self.assertTrue(result["reused_schema"])
        self.assertEqual(result["applied_migrations"], [])
        self.assertEqual(set(result["migrations"]), {"001_v4.sql", "002_v4_guard_completion.sql"})
        self.assertEqual(self.repo._owned("medication_entry_versions", entry["id"]), entry)

    def test_42_modified_applied_migration_is_rejected(self):
        original = self.db.execute("SELECT obj_description('msa'::regnamespace,'pg_namespace')").fetchone()[0]
        ledger = json.loads(original)
        ledger["migrations"]["002_v4_guard_completion.sql"] = "0" * 64
        with self.db.transaction():
            self.db.execute(sql.SQL("COMMENT ON SCHEMA msa IS {}").format(sql.Literal(json.dumps(ledger))))
            with self.assertRaisesRegex(RuntimeError, "checksum changed"):
                migrate(self.db)
            self.db.execute(sql.SQL("COMMENT ON SCHEMA msa IS {}").format(sql.Literal(original)))

    def test_43_workflow_question_cannot_reference_another_owner(self):
        foreign_intake = self.foreign.create_intake()
        workflow = self.repo.create_workflow(self.chat["id"], "PATIENT_SUMMARY")
        context = deepcopy(workflow["context"])
        context["pending_questions"] = [{"field_key": "medication", "question": "Which medication?",
                                         "target_id": str(foreign_intake["id"])}]
        with self.assertRaisesRegex(psycopg.Error, "another owner"):
            self.repo.transition_workflow(workflow["id"], "CLARIFYING", expected_revision=1, context=context)
        self.assertEqual(self.repo._owned("workflow_instances", workflow["id"])["revision"], 1)

    def test_44_ddi_source_cannot_disagree_with_retained_record(self):
        snap, _ = self.snapshot(0, 1)
        saved, _ = run_safety(self.repo, snap["id"], dataset())
        finding = self.repo._one("SELECT * FROM msa.safety_findings WHERE assessment_id=%s AND finding_type='DDI'", (saved["id"],))
        evidence = deepcopy(finding["evidence"])
        evidence["sources"][0]["record"]["original_level"] = "Minor"
        members = [UUID(r["entry_version_id"]) for r in evidence["component_refs"]]
        attempt = self.repo.start_assessment(snap["id"], saved["knowledge_builds"])
        with self.assertRaisesRegex(psycopg.Error, "differ from retained record"):
            self.repo.record_finding(attempt["id"], "forged", "DDI", "MAJOR", "Forged severity", evidence, members)
        self.assertEqual(self.db.execute("SELECT count(*) FROM msa.safety_findings WHERE assessment_id=%s", (attempt["id"],)).fetchone()[0], 0)

    def test_45_assessed_ddi_cannot_exceed_pinned_knowledge_scope(self):
        snap, _ = self.snapshot(0, 1)
        saved, _ = run_safety(self.repo, snap["id"], dataset())
        checks = deepcopy(saved["check_results"])
        checks["ddi"]["coverage"] = "ASSESSED"
        for key in ("ddi", "duplicate_ingredient"):
            for pair in checks[key]["pair_results"]:
                pair["source_record_refs"] = []
        attempt = self.repo.start_assessment(snap["id"], saved["knowledge_builds"])
        with self.assertRaisesRegex(psycopg.Error, "pinned knowledge scope"):
            self.repo.finish_assessment(attempt["id"], checks)

    def test_46_publication_checks_source_hash_against_manifest(self):
        ledger = read_ledger(self.db)
        tampered = deepcopy(ledger)
        tampered["builds"][self.build]["files"]["medications"] = "0" * 64
        with self.db.transaction():
            write_ledger(self.db, tampered)
            with self.assertRaisesRegex(psycopg.Error, "Source or manifest hash mismatch"):
                with self.db.transaction():
                    self.db.execute("SELECT msa.assert_ref_build(%s)", (self.build,))
            write_ledger(self.db, ledger)
