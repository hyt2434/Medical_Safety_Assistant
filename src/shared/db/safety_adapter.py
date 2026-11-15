"""Stream bounded Module 3 lookups into durable findings, preserving every approved target."""
from copy import deepcopy
from itertools import combinations, product
from uuid import UUID

from module3_interactions.engine import validate_component, valid_id
from .repository import empty_checks

SEVERITY = {"Major": "MAJOR", "Moderate": "MODERATE", "Minor": "MINOR", "Contraindicated": "CONTRAINDICATED"}


def finding_evidence(rule, sources=(), components=(), *, limitations=(), **extra):
    return {"schema": "finding-evidence.v4", "rule_id": rule, "rule_version": "core-module3-adapter-v4",
            "sources": list(sources), "component_refs": list(components), "limitations": list(limitations), **extra}


def run_safety(repo, snapshot, dataset, *, request_key=None, retry_of=None):
    rows = repo.snapshot_context(snapshot)
    coverage = deepcopy(dataset.coverage)
    deps = {"schema": "knowledge-builds.v4", "ddinter": {
        "index_sha256": coverage.get("index_sha256"), "manifest_sha256": coverage.get("collection_manifest_sha256"),
        "release": coverage.get("release"), "synthetic": bool(coverage.get("synthetic_fixture")),
        "loaded_scope": coverage}, "engine_config": {"lookup": "existing Module 3 dataset.lookup"},
        "limitations": [] if coverage.get("interaction_coverage_complete") else ["Loaded interaction coverage is not exhaustive"]}
    attempt = repo.start_assessment(snapshot, deps, request_key=request_key, retry_of=retry_of)
    if attempt["execution_status"] != "RUNNING":
        return attempt, {"reused_attempt": True, "checks": attempt["check_results"]}
    checks = empty_checks()
    pairs = list(combinations(rows, 2))
    for check in checks.values():
        if isinstance(check, dict):
            check["scope"] = {"loaded_coverage": coverage, "rule": "inter-medication occurrences only"}
            check["pair_results"] = [{"entry_version_ids": [str(a["entry_version_id"]), str(b["entry_version_id"])],
                                     "component_refs": [], "status": "UNASSESSED", "source_record_refs": [],
                                     "reason": "NOT_PROCESSED"} for a, b in pairs]
    resolved, finding_ids = {}, []
    failure = None

    def finalize_check(key):
        check = checks[key]
        check["execution"] = "COMPLETED"
        if not pairs:
            check["coverage"] = "NOT_APPLICABLE"
        else:
            complete = all(v["reliable" if key == "ddi" else "duplicate_reliable"] for v in resolved.values())
            if key == "ddi":
                complete = complete and bool(coverage.get("interaction_coverage_complete"))
            supported = any(p["status"] != "UNASSESSED" for p in check["pair_results"])
            complete = complete and all(p["status"] not in ("UNASSESSED", "SOURCE_CONFLICT", "NO_RECORD_IN_LOADED_SUBSET")
                                        for p in check["pair_results"])
            check["coverage"] = "ASSESSED" if complete else "PARTIAL" if supported else "UNASSESSED"
        check["limitations"] = sorted({reason for v in resolved.values() for reason in v["reasons"]})
        if key == "ddi":
            check["limitations"] += deps["limitations"]

    def record(key, kind, severity, explanation, evidence, entries=(), source_severity=None):
        saved = repo.record_finding(attempt["id"], key, kind, severity, explanation, evidence,
                                    [UUID(str(e)) for e in entries], source_severity=source_severity,
                                    next_step="Ask a qualified healthcare professional to review the finding and limitations")
        finding_ids.append(str(saved["id"]))
        return saved

    try:
        for row in rows:
            entry = str(row["entry_version_id"])
            ctx = row["component_context"]
            records = repo._all("SELECT * FROM msa_ref.ddinter_mappings WHERE id=ANY(%s::uuid[]) ORDER BY id",
                                ([r["mapping_id"] for r in ctx["mapping_refs"]],))
            components = []
            reasons = []
            for comp in ctx["components"]:
                mappings = [m for m in records if str(m["component_id"]) == comp["component_id"]]
                targets, approved_targets = {}, {}
                all_targets = {m["target_id"] for m in mappings if m["target_id"]}
                for mapping in mappings:
                    tid = mapping["target_id"]
                    if valid_id(tid):
                        approved_targets.setdefault(tid, []).append(mapping)
                    identity = dataset.identities.get(tid) if tid else None
                    if not identity:
                        reasons.append("MAPPING_TARGET_MISSING_OR_OUTSIDE_LOADED_IDENTITY_SCOPE")
                        continue
                    med = {"medication_id": entry, "prescription_ids": [str(row["item_id"])],
                           "identity_status": "VERIFIED" if ctx["identification_status"] == "SELECTED" else "REVIEW_REQUIRED",
                           "identity_evidence": [{"product_id": ctx["product_id"], "build": ctx["reference_build"]}]}
                    mapped = {"name": identity["name"], "ddinter_id": tid, "mapping_status": "VERIFIED",
                              "mapping_evidence": [mapping["source_locator"], *mapping["retrieval_evidence"]]}
                    validated = validate_component(med, mapped, len(components), dataset)
                    if validated["status"] != "VERIFIED_FOR_PAIR_LOOKUP":
                        reasons.extend(validated["issues"])
                        continue
                    targets.setdefault(tid, []).append(mapping)
                if len(all_targets) > 1:
                    reasons.append("MULTIPLE_APPROVED_TARGETS_APPLICABILITY_NOT_DISAMBIGUATED")
                if not mappings:
                    reasons.append("NO_MAPPING_RECORD_FOR_COMPONENT")
                components.append({"id": comp["component_id"], "targets": targets, "approved_targets": approved_targets,
                                   "reliable": len(all_targets) == 1 and len(targets) == 1
                                   and all(m["target_id"] for m in mappings),
                                   "duplicate_reliable": len(all_targets) == 1 and len(approved_targets) == 1
                                   and all(m["target_id"] for m in mappings)})
            reliable = (ctx["component_coverage"] == "COMPLETE" and bool(components)
                        and all(c["reliable"] for c in components))
            duplicate_reliable = (ctx["component_coverage"] == "COMPLETE" and bool(components)
                                  and all(c["duplicate_reliable"] for c in components))
            resolved[entry] = {"components": components, "reliable": reliable, "duplicate_reliable": duplicate_reliable,
                               "reasons": sorted(set(reasons))}
            if not reliable:
                record("unresolved:" + entry, "UNRESOLVED", "UNKNOWN",
                       "Identity/mapping coverage is incomplete; all source mappings remain retained",
                       finding_evidence("identity-coverage", limitations=reasons), [entry])

        # Duplicate rule is independent of pair lookup errors. Same DDInter ID is a review signal, not a dose total.
        for index, (a, b) in enumerate(pairs):
            left, right = str(a["entry_version_id"]), str(b["entry_version_id"])
            l, r = resolved[left], resolved[right]
            output = checks["duplicate_ingredient"]["pair_results"][index]
            refs = []
            for lc, rc in product(l["components"], r["components"]):
                for target in sorted(set(lc["approved_targets"]) & set(rc["approved_targets"])):
                    component_refs = [{"entry_version_id": left, "component_id": lc["id"]},
                                      {"entry_version_id": right, "component_id": rc["id"]}]
                    mapping_rows = lc["approved_targets"][target] + rc["approved_targets"][target]
                    finding = record(f"duplicate:{left}:{right}:{lc['id']}:{rc['id']}:{target}",
                                     "DUPLICATE_INGREDIENT", "UNKNOWN",
                                     "Possible duplicate exposure for a source-supported target; administration and intentionality are not assessed",
                                     finding_evidence("same-approved-ddinter-target",
                                         [m["source_locator"] for m in mapping_rows], component_refs,
                                         limitations=l["reasons"] + r["reasons"], target_id=target,
                                         mapping_ids=[str(m["id"]) for m in mapping_rows]), [left, right])
                    refs.append({"finding_id": str(finding["id"]), "source_index": 0})
                    output["component_refs"].extend(component_refs)
            output.update(status="DUPLICATE_DETECTED" if refs else "NO_DUPLICATE_IN_ASSESSED_SCOPE" if l["duplicate_reliable"] and r["duplicate_reliable"] else "UNASSESSED",
                          reason=None if l["duplicate_reliable"] and r["duplicate_reliable"] else "INCOMPLETE_COMPONENT_IDENTITY",
                          source_record_refs=refs)

        finalize_check("duplicate_ingredient")
        checks["ddi"]["execution"] = "RUNNING"
        # Each positive finding is committed before the next fallible dataset lookup.
        for index, (a, b) in enumerate(pairs):
            left, right = str(a["entry_version_id"]), str(b["entry_version_id"])
            l, r = resolved[left], resolved[right]
            output = checks["ddi"]["pair_results"][index]
            evaluated, positive, conflict = 0, False, False
            for lc, rc in product(l["components"], r["components"]):
                for lt, rt in product(sorted(lc["targets"]), sorted(rc["targets"])):
                    if lt == rt:
                        continue
                    looked = dataset.lookup(lt, rt)
                    evaluated += 1
                    component_refs = [{"entry_version_id": left, "component_id": lc["id"]},
                                      {"entry_version_id": right, "component_id": rc["id"]}]
                    if looked["status"] in ("INTERACTION_DETECTED", "CONFLICTING_SOURCE_RECORDS"):
                        sources = []
                        for record_row in looked["source_records"]:
                            proof = record_row["evidence"]
                            sources.append({"target_ids": record_row["drug_id_pair"],
                                            "source_severity": record_row["original_level"],
                                            "artifact_sha256": proof["csv_sha256"],
                                            "locator": {"uri": proof.get("source_url"), "filename": proof.get("filename"),
                                                        "csv_record_1_based": proof.get("csv_record_1_based")},
                                            "record": record_row})
                        is_conflict = looked["status"] == "CONFLICTING_SOURCE_RECORDS"
                        label = looked.get("original_level")
                        all_mapping_rows = lc["targets"][lt] + rc["targets"][rt]
                        finding = record(f"ddi:{left}:{right}:{lc['id']}:{rc['id']}:{lt}:{rt}",
                            "SOURCE_CONFLICT" if is_conflict else "DDI", SEVERITY.get(label, "UNKNOWN"),
                            "Conflicting DDInter source levels require review" if is_conflict else
                            "DDInter source interaction for an approved target combination; applicability and incomplete coverage require review",
                            finding_evidence("existing-module3-dataset-lookup", sources, component_refs,
                                limitations=l["reasons"] + r["reasons"] + deps["limitations"],
                                mapping_ids=[str(m["id"]) for m in all_mapping_rows]), [left, right], source_severity=label)
                        output["source_record_refs"].extend({"finding_id": str(finding["id"]), "source_index": n}
                                                            for n in range(len(sources)))
                        output["component_refs"].extend(component_refs)
                        positive = positive or not is_conflict
                        conflict = conflict or is_conflict
                        # Preserve the partial pair outcome even if the next combination fails.
                        output.update(status="SOURCE_CONFLICT" if conflict else "INTERACTION_DETECTED", reason=None)
            if not positive and not conflict:
                output.update(status="NO_RECORD_IN_LOADED_SUBSET" if evaluated else "UNASSESSED",
                              reason="No source pair in loaded scope" if evaluated else "No reliable non-self target pair")

        finalize_check("ddi")
    except Exception as exc:
        failure = {"schema": "error.v4", "code": type(exc).__name__, "message": str(exc), "details": None}
        for key in ("ddi", "duplicate_ingredient"):
            check = checks[key]
            if check["execution"] == "COMPLETED":
                continue
            check["execution"], check["error"] = "FAILED", failure
            supported = any(p["status"] != "UNASSESSED" for p in check["pair_results"])
            check["coverage"] = "PARTIAL" if supported else "UNASSESSED"
            check["limitations"].append("A processing error interrupted this attempt; committed findings remain available")
    saved = repo.finish_assessment(attempt["id"], checks, error=failure)
    return saved, {"schema": "core-safety.v4", "findings": finding_ids, "checks": checks,
                   "safe_to_take": None, "no_interactions": None, "requires_hcp_review": True,
                   "autonomous_prescribing": False, "automated_schedule_optimization": False}
