"""V4 transactional persistence. authenticated_owner must come from trusted server identity."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def now():
    return datetime.now(timezone.utc)


def empty_checks():
    return {"schema": "checks.v4", **{k: {"execution": "NOT_STARTED", "coverage": "PENDING",
            "scope": {}, "pair_results": [], "limitations": [], "error": None}
            for k in ("ddi", "duplicate_ingredient")}}


class CoreRepository:
    def __init__(self, connection, *, authenticated_owner):
        self.db = connection
        self.owner = UUID(str(authenticated_owner))
        if not connection.autocommit:
            raise ValueError("Autocommit connection required; public operations own independent transactions")

    def _one(self, query, params=()):
        with self.db.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def _all(self, query, params=()):
        with self.db.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @contextmanager
    def transaction(self):
        if self.db.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("Do not wrap Core public operations in an outer transaction; warnings must commit independently")
        with self.db.transaction():
            self.db.execute("SELECT set_config('msa.authenticated_owner',%s,true)", (str(self.owner),))
            yield

    def _insert(self, table, **values):
        prepared = {k: Jsonb(v) if isinstance(v, (dict, list)) else v for k, v in values.items()}
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(*table.split(".")),
            sql.SQL(",").join(map(sql.Identifier, prepared)),
            sql.SQL(",").join(sql.Placeholder() for _ in prepared))
        return self._one(query, tuple(prepared.values()))

    def _owned(self, table, identity, *, lock=False):
        row = self._one(sql.SQL("SELECT * FROM msa.{} WHERE id=%s AND user_id=%s" + (" FOR UPDATE" if lock else "")).format(
            sql.Identifier(table)), (identity, self.owner))
        if not row:
            raise PermissionError("Record missing or outside authenticated owner")
        return row

    def digest(self, value):
        return self._one("SELECT msa.digest(%s) AS digest", (Jsonb(value),))["digest"]

    def create_conversation(self):
        with self.transaction():
            return self._insert("msa.conversation_sessions", user_id=self.owner)

    def _message(self, conversation, role, body, metadata=None):
        self._owned("conversation_sessions", conversation, lock=True)
        ordinal = self._one("SELECT coalesce(max(sequence_no),0)+1 AS n FROM msa.conversation_messages WHERE conversation_id=%s",
                            (conversation,))["n"]
        return self._insert("msa.conversation_messages", user_id=self.owner, conversation_id=conversation,
                            sequence_no=ordinal, role=role, text_content=body,
                            metadata=metadata or {"schema": "message.v4", "content_refs": []})

    def append_message(self, conversation, role, body, metadata=None):
        with self.transaction():
            return self._message(conversation, role, body, metadata)

    def create_intake(self, conversation=None, *, purpose="MEDICATION_COLLECTION"):
        with self.transaction():
            if conversation:
                self._owned("conversation_sessions", conversation)
            return self._insert("msa.intake_sessions", user_id=self.owner, conversation_id=conversation, purpose=purpose)

    def create_workflow(self, conversation, workflow_type, *, intake=None, origin_message=None):
        with self.transaction():
            self._owned("conversation_sessions", conversation)
            return self._insert("msa.workflow_instances", user_id=self.owner, conversation_id=conversation,
                                intake_session_id=intake, origin_message_id=origin_message, workflow_type=workflow_type,
                                fsm_version="core-workflow-v4")

    def transition_workflow(self, workflow, state, *, expected_revision, context=None):
        with self.transaction():
            row = self._owned("workflow_instances", workflow, lock=True)
            if row["revision"] != expected_revision:
                raise ValueError("Stale workflow revision")
            if state == "COMPLETED" and row["workflow_type"] == "PATIENT_SUMMARY":
                raise ValueError("Save summary through exact owner confirmation")
            next_context = deepcopy(context if context is not None else row["context"])
            if state != "AWAITING_CONFIRMATION":
                next_context["pending_confirmation"] = None
            return self._one("UPDATE msa.workflow_instances SET state=%s,context=%s,revision=revision+1 WHERE id=%s RETURNING *",
                             (state, Jsonb(next_context), workflow))

    def record_input(self, intake, modality, original_bytes, *, payload, content_type=None, message=None):
        with self.transaction():
            self._owned("intake_sessions", intake, lock=True)
            return self._insert("msa.intake_inputs", user_id=self.owner, session_id=intake,
                                message_id=message, modality=modality, content_type=content_type,
                                payload_or_locator=payload, input_digest=hashlib.sha256(original_bytes).hexdigest())

    def record_extraction(self, input_id, extractor_name, extractor_version, result, *, status="SUCCEEDED", errors=None):
        with self.transaction():
            self._owned("intake_inputs", input_id, lock=True)
            n = self._one("SELECT coalesce(max(attempt_no),0)+1 AS n FROM msa.intake_extractions WHERE input_id=%s", (input_id,))["n"]
            return self._insert("msa.intake_extractions", user_id=self.owner, input_id=input_id, attempt_no=n,
                                extractor_name=extractor_name, extractor_version=extractor_version,
                                status=status, result=result, errors=errors)

    def create_item(self, extraction, ordinal, medication_fields, *, locator=None):
        with self.transaction():
            parent = self._owned("intake_extractions", extraction)
            evidence = {"schema": "item-origin.v4", "input_id": str(parent["input_id"]),
                        "extraction_id": str(extraction), "item_ordinal": ordinal,
                        "locator": locator or {}, "text_raw": medication_fields.get("evidence_text")}
            item = self._insert("msa.intake_items", user_id=self.owner, extraction_id=extraction,
                                item_ordinal=ordinal, origin_evidence=evidence)
            return self._insert("msa.medication_entry_versions", user_id=self.owner, item_id=item["id"], version_no=1,
                                source_extraction_id=extraction, medication_fields=medication_fields)

    def correct_entry(self, entry, medication_fields, *, source_extraction=None):
        with self.transaction():
            prior = self._owned("medication_entry_versions", entry)
            self._owned("intake_items", prior["item_id"], lock=True)
            return self._insert("msa.medication_entry_versions", user_id=self.owner, item_id=prior["item_id"],
                                supersedes_version_id=entry, version_no=prior["version_no"] + 1,
                                source_extraction_id=source_extraction, medication_fields=medication_fields)

    def confirm_entry(self, entry, displayed_digest, request_key, *, explicit_confirmation):
        if explicit_confirmation is not True:
            raise ValueError("Explicit authenticated-owner action required")
        with self.transaction():
            current = self._owned("medication_entry_versions", entry)
            self._owned("intake_items", current["item_id"], lock=True)
            saved = self._one("SELECT * FROM msa.medication_entry_versions WHERE user_id=%s AND confirmation_key=%s",
                              (self.owner, request_key))
            if saved:
                if saved["id"] != UUID(str(entry)) or saved["content_digest"] != displayed_digest:
                    raise ValueError("Confirmation key reused for another payload/version")
                return saved
            self.db.execute("SELECT set_config('msa.displayed_digest',%s,true)", (displayed_digest,))
            return self._one("UPDATE msa.medication_entry_versions SET confirmed_at=clock_timestamp(),confirmation_key=%s WHERE id=%s RETURNING *",
                             (request_key, entry))

    def record_match(self, entry, outcome, *, product=None, candidates=(), reference_build=None,
                     matcher_version="core-reference-v4", evidence=None, confidence=None):
        with self.transaction():
            self._owned("medication_entry_versions", entry, lock=True)
            n = self._one("SELECT coalesce(max(attempt_no),0)+1 AS n FROM msa.entry_matches WHERE entry_version_id=%s", (entry,))["n"]
            if product and reference_build is None:
                p = self._one("SELECT dataset_build FROM msa_ref.medications WHERE id=%s", (product,))
                if not p:
                    raise ValueError("Unknown Core product")
                reference_build = p["dataset_build"]
            basis = evidence or {"schema": "match-evidence.v4", "method": matcher_version,
                                 "qualifiers": {}, "external_candidates": [], "candidate_evidence": [],
                                 "outcome_reason": None, "limitations": []}
            for rank, candidate in enumerate(candidates, 1):
                self._insert("msa.entry_matches", user_id=self.owner, entry_version_id=entry, attempt_no=n,
                             match_status="CANDIDATE", candidate_rank=rank, product_id=candidate,
                             reference_build=reference_build, matcher_version=matcher_version,
                             confidence=None, match_evidence=basis)
            return self._insert("msa.entry_matches", user_id=self.owner, entry_version_id=entry, attempt_no=n,
                                match_status=outcome, product_id=product, reference_build=reference_build,
                                matcher_version=matcher_version, confidence=confidence, match_evidence=basis)

    def create_snapshot(self, entries, *, context_key="CURRENT_MEDICATIONS", data_context="PATIENT",
                        as_of=None, supersedes=None):
        with self.transaction():
            snap = self._insert("msa.medication_list_snapshots", user_id=self.owner, context_key=context_key,
                                data_context=data_context, as_of_at=as_of or now(), supersedes_snapshot_id=supersedes)
            for entry_id, match_id in entries:
                entry = self._owned("medication_entry_versions", entry_id)
                match = self._owned("entry_matches", match_id) if match_id else None
                context = {"schema": "snapshot-entry.v4", "input_content_digest": entry["content_digest"],
                           "identification_status": match["match_status"] if match else "NOT_ATTEMPTED",
                           "product_id": None, "reference_build": match["reference_build"] if match else None,
                           "component_coverage": "UNKNOWN", "components": [], "mapping_refs": [],
                           "limitations": []}
                if match and match["match_status"] == "SELECTED":
                    product = self._one("SELECT * FROM msa_ref.medications WHERE id=%s", (match["product_id"],))
                    components = self._all("SELECT msa.component_document(c) AS doc FROM msa_ref.medication_ingredients c WHERE medication_id=%s ORDER BY ordinal",
                                           (product["id"],))
                    refs = self._all("""SELECT d.id,d.component_id FROM msa_ref.ddinter_mappings d
                        JOIN msa_ref.medication_ingredients c ON c.id=d.component_id
                        WHERE c.medication_id=%s AND d.dataset_build=%s ORDER BY d.id""", (product["id"], product["dataset_build"]))
                    context.update(product_id=str(product["id"]), reference_build=product["dataset_build"],
                                   components=[c["doc"] for c in components],
                                   mapping_refs=[{"mapping_id": str(r["id"]), "component_id": str(r["component_id"])} for r in refs],
                                   component_coverage="COMPLETE" if components and product["component_count"] == len(components) else "PARTIAL")
                else:
                    context["limitations"].append("Product identity is unresolved or not attempted")
                self._insert("msa.snapshot_entries", snapshot_id=snap["id"], entry_version_id=entry_id,
                             user_id=self.owner, entry_match_id=match_id, component_context=context)
            return self._one("UPDATE msa.medication_list_snapshots SET status='SEALED' WHERE id=%s RETURNING *", (snap["id"],))

    def snapshot_context(self, snapshot):
        self._owned("medication_list_snapshots", snapshot)
        return self._all("""SELECT e.*,v.item_id,v.medication_fields FROM msa.snapshot_entries e
            JOIN msa.medication_entry_versions v ON v.id=e.entry_version_id
            WHERE e.snapshot_id=%s AND e.user_id=%s ORDER BY e.entry_version_id""", (snapshot, self.owner))

    def start_assessment(self, snapshot, knowledge, *, engine_version="core-module3-adapter-v4", request_key=None, retry_of=None):
        with self.transaction():
            snap = self._owned("medication_list_snapshots", snapshot)
            deps = deepcopy(knowledge)
            builds = self._all("""SELECT DISTINCT component_context->>'reference_build' AS build FROM msa.snapshot_entries
                WHERE snapshot_id=%s AND component_context->>'reference_build' IS NOT NULL ORDER BY build""", (snapshot,))
            deps.update(schema="knowledge-builds.v4", snapshot_digest=snap["snapshot_digest"],
                        reference_builds=[r["build"] for r in builds], hash_contract="pg-jsonb-text-v4")
            request_key = request_key or uuid4()
            previous = self._one("SELECT * FROM msa.safety_assessments WHERE user_id=%s AND request_key=%s", (self.owner, request_key))
            if previous:
                if previous["snapshot_id"] != UUID(str(snapshot)) or previous["knowledge_builds"] != deps or previous["engine_version"] != engine_version or previous["retry_of_assessment_id"] != retry_of:
                    raise ValueError("Assessment request key reused for different dependencies")
                return previous
            return self._insert("msa.safety_assessments", user_id=self.owner, snapshot_id=snapshot,
                                retry_of_assessment_id=retry_of, request_key=request_key, engine_version=engine_version,
                                knowledge_builds=deps, check_results=empty_checks())

    def record_finding(self, assessment, key, kind, severity, explanation, evidence, entries=(),
                       *, source_severity=None, next_step=None, prior_finding=None):
        with self.transaction():
            attempt = self._owned("safety_assessments", assessment, lock=True)
            existing = self._one("SELECT * FROM msa.safety_findings WHERE assessment_id=%s AND finding_key=%s", (assessment, key))
            if existing:
                links = self._all("SELECT entry_version_id FROM msa.finding_entries WHERE finding_id=%s ORDER BY entry_version_id", (existing["id"],))
                if any((existing["finding_type"] != kind, existing["severity"] != severity,
                        existing["evidence"] != evidence, existing["explanation"] != explanation,
                        [str(r["entry_version_id"]) for r in links] != sorted(map(str, entries)))):
                    raise ValueError("Finding key reused for different content")
                return existing
            finding = self._insert("msa.safety_findings", user_id=self.owner, assessment_id=assessment,
                                   snapshot_id=attempt["snapshot_id"], prior_finding_id=prior_finding,
                                   finding_key=key, finding_type=kind, severity=severity, source_severity=source_severity,
                                   explanation=explanation, recommended_next_step=next_step, evidence=evidence)
            for entry in entries:
                self._insert("msa.finding_entries", finding_id=finding["id"], entry_version_id=entry,
                             snapshot_id=attempt["snapshot_id"], user_id=self.owner)
            return finding

    def finish_assessment(self, assessment, checks, *, error=None):
        with self.transaction():
            self._owned("safety_assessments", assessment, lock=True)
            return self._one("""UPDATE msa.safety_assessments SET execution_status=%s,check_results=%s,error_details=%s
                WHERE id=%s RETURNING *""", ("FAILED" if error else "COMPLETED", Jsonb(checks), Jsonb(error) if error else None, assessment))

    def severe_warnings(self):
        return self._all("""SELECT * FROM msa.safety_findings WHERE user_id=%s AND
            (severity IN ('MAJOR','CONTRAINDICATED') OR (finding_type='SOURCE_CONFLICT' AND EXISTS(
             SELECT 1 FROM jsonb_array_elements(evidence->'sources') s
             WHERE s->>'source_severity' IN ('Major','Contraindicated')))) ORDER BY recorded_at""", (self.owner,))

    def record_health_source(self, content, *, message=None, locator=None, origin="PATIENT_REPORTED",
                             verification="REPORTED", source_date=None, supersedes=None, corrects=None):
        with self.transaction():
            where = deepcopy(locator) if locator else {"schema": "health-source-locator.v4", "message_id": str(message)}
            return self._insert("msa.patient_health_sources", user_id=self.owner, message_id=message,
                                source_content=content, source_locator=where, origin=origin, verification_status=verification,
                                source_date=source_date, supersedes_source_id=supersedes, corrects_source_id=corrects)

    def manifest_source(self, kind, identity, key, *, scope="Exact retained record"):
        tables = {"HEALTH_SOURCE": ("patient_health_sources", "content_digest"), "ENTRY_VERSION": ("medication_entry_versions", "content_digest"),
                  "SNAPSHOT": ("medication_list_snapshots", "snapshot_digest"), "ASSESSMENT": ("safety_assessments", "result_digest"),
                  "FINDING": ("safety_findings", None)}
        table, column = tables[kind]
        row = self._owned(table, identity)
        digest = row[column] if column else self._one("SELECT msa.digest(msa.finding_document(%s)) AS digest", (identity,))["digest"]
        if not digest:
            raise ValueError("Source is not terminal/confirmed")
        if kind == "ENTRY_VERSION" and row["confirmed_at"] is None:
            raise ValueError("Source entry is not confirmed")
        return {"key": key, "kind": kind, "id": str(identity), "digest": digest, "scope": scope}

    def prepare_summary(self, workflow, content, manifest, generation_context, *, expected_revision):
        with self.transaction():
            row = self._owned("workflow_instances", workflow, lock=True)
            if row["workflow_type"] != "PATIENT_SUMMARY" or row["revision"] != expected_revision or row["state"] not in ("COLLECTING", "CLARIFYING", "AWAITING_CONFIRMATION"):
                raise ValueError("Wrong or stale summary workflow")
            self.db.execute("SELECT msa.validate_manifest(%s,%s)", (Jsonb(manifest), self.owner))
            digest = self._one("SELECT msa.summary_digest(%s,%s) AS digest", (Jsonb(content), Jsonb(manifest)))["digest"]
            display = self._message(row["conversation_id"], "ASSISTANT", json.dumps({"summary": content, "sources": manifest}, ensure_ascii=False, sort_keys=True))
            revision = row["revision"] + 1
            context = deepcopy(row["context"])
            context["draft"] = {"draft_revision": revision, "content": content, "source_manifest": manifest,
                                "display_message_id": str(display["id"]), "generated_at": now().isoformat(),
                                "generation_context": generation_context}
            context["pending_confirmation"] = {"draft_revision": revision, "payload_digest": digest, "display_message_id": str(display["id"])}
            return self._one("""UPDATE msa.workflow_instances SET state='AWAITING_CONFIRMATION',context=%s,revision=revision+1 WHERE id=%s RETURNING *""",
                             (Jsonb(context), workflow))

    def confirm_summary(self, workflow, displayed_digest, draft_revision, request_key, *, explicit_confirmation,
                        supersedes=None, snapshot=None, assessment=None):
        if explicit_confirmation is not True:
            raise ValueError("Explicit authenticated-owner action required")
        with self.transaction():
            row = self._owned("workflow_instances", workflow, lock=True)
            saved = self._one("SELECT * FROM msa.patient_health_summaries WHERE user_id=%s AND confirmation_key=%s", (self.owner, request_key))
            if saved:
                if any((saved["workflow_id"] != UUID(str(workflow)), saved["draft_revision"] != draft_revision,
                        saved["confirmation_digest"] != displayed_digest, saved["supersedes_summary_id"] != supersedes,
                        saved["medication_snapshot_id"] != snapshot, saved["primary_assessment_id"] != assessment)):
                    raise ValueError("Summary confirmation key reused")
                return saved
            pending = row["context"].get("pending_confirmation")
            if row["state"] != "AWAITING_CONFIRMATION" or not pending or pending["payload_digest"] != displayed_digest or pending["draft_revision"] != draft_revision:
                raise ValueError("Stale summary confirmation")
            draft = row["context"]["draft"]
            key = uuid4()
            root, version = key, 1
            if supersedes:
                prior = self._owned("patient_health_summaries", supersedes)
                root, version = prior["series_root_id"], prior["version_no"] + 1
                self._owned("patient_health_summaries", root, lock=True)
            self.db.execute("SELECT set_config('msa.displayed_digest',%s,true)", (displayed_digest,))
            summary = self._insert("msa.patient_health_summaries", id=key, user_id=self.owner,
                                   series_root_id=root, supersedes_summary_id=supersedes, version_no=version,
                                   workflow_id=workflow, draft_revision=draft_revision, medication_snapshot_id=snapshot,
                                   primary_assessment_id=assessment, summary_content=draft["content"],
                                   source_manifest=draft["source_manifest"], confirmation_key=request_key,
                                   generation_context=draft["generation_context"],
                                   generated_at=datetime.fromisoformat(draft["generated_at"]), confirmed_at=now())
            context = deepcopy(row["context"])
            context["pending_confirmation"] = None
            self.db.execute("UPDATE msa.workflow_instances SET state='COMPLETED',context=%s,revision=revision+1 WHERE id=%s",
                            (Jsonb(context), workflow))
            return summary

    def summary_history(self, root):
        return self._all("SELECT * FROM msa.patient_health_summaries WHERE user_id=%s AND series_root_id=%s ORDER BY version_no", (self.owner, root))
