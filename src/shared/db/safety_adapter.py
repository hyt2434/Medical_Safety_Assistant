"""Stream verified Module 3 lookups into durable Core V4 findings."""
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
    builds = {r['component_context']['reference_build'] for r in rows
              if r['component_context']['reference_build']}
    if len(builds) > 1:
        raise ValueError('One consistent reference dataset build is required')
    mapping_ids = [ref['mapping_id'] for row in rows for ref in row['component_context']['mapping_refs']]
    pinned_mappings = repo._all('SELECT * FROM msa_ref.ddinter_mappings WHERE id=ANY(%s::uuid[]) ORDER BY id',
                               (mapping_ids,))
    if len(pinned_mappings) != len(set(mapping_ids)) or any(m['dataset_build'] not in builds for m in pinned_mappings):
        raise ValueError('Frozen mapping dependencies differ from pinned reference build')
    coverage = deepcopy(dataset.coverage)
    if not coverage.get('synthetic_fixture') and (len(coverage.get('source_artifacts', [])) != 8 or
            any(not coverage.get(key) for key in ('index_sha256', 'collection_manifest_sha256', 'index_manifest_sha256'))):
        raise ValueError('Real assessments require the hash-verified eight-CSV DDInter index; no sample fallback')
    deps = {"schema": "knowledge-builds.v4", "ddinter": {
        "index_sha256": coverage.get("index_sha256"), "manifest_sha256": coverage.get("collection_manifest_sha256"),
        'index_manifest_sha256': coverage.get('index_manifest_sha256'),
        'mapping_catalog_sha256': sorted({m['target_catalog_sha256'] for m in pinned_mappings}),
        "release": coverage.get("release"), "synthetic": bool(coverage.get("synthetic_fixture")),
        "loaded_scope": coverage}, "engine_config": {"lookup": "existing Module 3 dataset.lookup",
            'rules': 'module3-mvp-v1', 'duplicate_identity': 'exact-local-id-or-approved-ddinter-target'},
        "limitations": [] if coverage.get("interaction_coverage_complete") else ["Loaded interaction coverage is not exhaustive"]}
    attempt = repo.start_assessment(snapshot, deps, request_key=request_key, retry_of=retry_of)
    if attempt["execution_status"] != "RUNNING":
        return attempt, {"reused_attempt": True, "checks": attempt["check_results"],
                         "reminder_hold": attempt['check_results']['ddi']['scope'].get('reminder_hold')}
    checks = empty_checks()
    pairs = list(combinations(rows, 2))
    for check in checks.values():
        if isinstance(check, dict):
            check["scope"] = {"loaded_coverage": coverage, "rule": "inter-medication occurrences only"}
            check['scope']['component_pair_results'] = []
            check["pair_results"] = [{"entry_version_ids": [str(a["entry_version_id"]), str(b["entry_version_id"])],
                                     "component_refs": [], "status": "UNASSESSED", "source_record_refs": [],
                                     "reason": "NOT_PROCESSED"} for a, b in pairs]
    resolved, finding_ids = {}, []
    failure = None
    hold = {'required': False, 'scope': 'NEW_IMPLICATED_ACTIVATIONS_ONLY',
            'entry_version_ids': [], 'finding_ids': [], 'existing_reminders_modified': False,
            'activation_policy_implemented': False}
    checks['ddi']['scope']['reminder_hold'] = hold

    def finalize_check(key):
        check = checks[key]
        check["execution"] = "COMPLETED"
        if not pairs:
            check["coverage"] = "NOT_APPLICABLE"
        else:
            complete = all(v["reliable" if key == "ddi" else "duplicate_reliable"] for v in resolved.values())
            if key == "ddi":
                complete = complete and bool(coverage.get("interaction_coverage_complete"))
            else:
                complete = complete and all(p['identity_complete'] for p in check['scope']['component_pair_results'])
            supported = any(p["status"] != "UNASSESSED" for p in check["pair_results"])
            complete = complete and all(p["status"] not in ("UNASSESSED", "SOURCE_CONFLICT", "NO_RECORD_IN_LOADED_SUBSET")
                                        for p in check["pair_results"])
            check["coverage"] = "ASSESSED" if complete else "PARTIAL" if supported else "UNASSESSED"
        check["limitations"] = sorted({reason for v in resolved.values() for reason in v["reasons"]})
        if key == "ddi":
            check["limitations"] += deps["limitations"]

    def record(key, kind, severity, explanation, evidence, entries=(), source_severity=None):
        evidence = deepcopy(evidence)
        severe = severity in {'MAJOR', 'CONTRAINDICATED'} or (kind == 'SOURCE_CONFLICT' and any(
            s.get('source_severity') in {'Major', 'Contraindicated'} for s in evidence['sources']))
        evidence.update(display_timing='IMMEDIATE', wait_for_hcp_before_display=False,
                        autonomous_medication_changes=False, reminder_hold={
                            'required': severe, 'scope': 'NEW_IMPLICATED_ACTIVATIONS_ONLY',
                            'entry_version_ids': sorted(map(str, entries)) if severe else [],
                            'activation_policy_implemented': False, 'existing_reminders_modified': False})
        saved = repo.record_finding(attempt["id"], key, kind, severity, explanation, evidence,
                                    [UUID(str(e)) for e in entries], source_severity=source_severity,
                                    next_step="Ask a qualified healthcare professional to review the finding and limitations")
        finding_ids.append(str(saved["id"]))
        if severe:
            hold['required'] = True
            hold['entry_version_ids'] = sorted(set(hold['entry_version_ids']) | set(map(str, entries)))
            hold['finding_ids'].append(str(saved['id']))
        return saved

    try:
        for row in rows:
            entry = str(row["entry_version_id"])
            ctx = row["component_context"]
            record_ids = {r['mapping_id'] for r in ctx['mapping_refs']}
            records = [m for m in pinned_mappings if str(m['id']) in record_ids]
            components = []
            reasons = []
            for comp in ctx["components"]:
                retained = repo._one('SELECT * FROM msa_ref.medication_ingredients WHERE id=%s',
                                     (comp['component_id'],))
                if (not retained or retained['dataset_build'] != ctx['reference_build']
                        or str(retained['medication_id']) != ctx['product_id']
                        or (str(retained['ingredient_id']) if retained['ingredient_id'] else None) != comp['ingredient_id']):
                    raise ValueError('Frozen component differs from pinned reference build')
                local = repo._one('SELECT * FROM msa_ref.ingredients WHERE id=%s AND dataset_build=%s',
                                  (comp['ingredient_id'], ctx['reference_build'])) if comp['ingredient_id'] else None
                mappings = [m for m in records if str(m["component_id"]) == comp["component_id"]]
                if any(m['dataset_build'] != ctx['reference_build'] for m in mappings):
                    raise ValueError('Mapping differs from pinned reference build')
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
                                   'local_ingredient': local,
                                   "reliable": len(all_targets) == 1 and len(targets) == 1
                                   and all(m["target_id"] for m in mappings),
                                   "duplicate_reliable": bool(local) or (len(all_targets) == 1 and len(approved_targets) == 1
                                   and all(m["target_id"] for m in mappings))})
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
            component_start = len(checks['duplicate_ingredient']['scope']['component_pair_results'])
            for lc, rc in product(l["components"], r["components"]):
                common = sorted(set(lc['approved_targets']) & set(rc['approved_targets']))
                local_same = (lc['local_ingredient'] and rc['local_ingredient']
                              and lc['local_ingredient']['id'] == rc['local_ingredient']['id'])
                assessed = (bool(lc['local_ingredient'] and rc['local_ingredient']) or
                            (lc['duplicate_reliable'] and rc['duplicate_reliable']
                             and bool(lc['approved_targets']) and bool(rc['approved_targets'])))
                component_refs = [{'entry_version_id': left, 'component_id': lc['id']},
                                  {'entry_version_id': right, 'component_id': rc['id']}]
                checks['duplicate_ingredient']['scope']['component_pair_results'].append({
                    'component_refs': component_refs, 'status': 'DUPLICATE_DETECTED' if local_same or common else
                    'NO_DUPLICATE_IN_ASSESSED_SCOPE' if assessed else 'UNASSESSED',
                    'identity_complete': bool(local_same) or (assessed and (not common or
                        len(lc['approved_targets']) == len(rc['approved_targets']) == 1)),
                    'identity_scope': 'Exact local ingredient IDs or approved DDInter targets; no chemical equivalence'})
                for target in ([None] if local_same else common):
                    component_refs = [{"entry_version_id": left, "component_id": lc["id"]},
                                      {"entry_version_id": right, "component_id": rc["id"]}]
                    mapping_rows = lc['approved_targets'].get(target, []) + rc['approved_targets'].get(target, [])
                    sources = ([lc['local_ingredient']['source_locator'], rc['local_ingredient']['source_locator']]
                               if local_same else [m['source_locator'] for m in mapping_rows])
                    finding = record(f"duplicate:{left}:{right}:{lc['id']}:{rc['id']}:{target}",
                                     "DUPLICATE_INGREDIENT", "UNKNOWN",
                                     "Possible duplicate exposure for an exact local ingredient ID or approved DDInter target; administration and intentionality are not assessed",
                                     finding_evidence('same-local-ingredient-id' if local_same else "same-approved-ddinter-target",
                                         sources, component_refs,
                                         limitations=l["reasons"] + r["reasons"], target_id=target,
                                         local_ingredient_id=str(lc['local_ingredient']['id']) if local_same else None,
                                         mapping_ids=[str(m["id"]) for m in mapping_rows]), [left, right])
                    refs.append({"finding_id": str(finding["id"]), "source_index": 0})
                    output["component_refs"].extend(component_refs)
            component_outputs = checks['duplicate_ingredient']['scope']['component_pair_results'][component_start:]
            pair_complete = (bool(component_outputs) and all(p['status'] != 'UNASSESSED' for p in component_outputs)
                             and a['component_context']['component_coverage'] == b['component_context']['component_coverage'] == 'COMPLETE')
            output.update(status="DUPLICATE_DETECTED" if refs else "NO_DUPLICATE_IN_ASSESSED_SCOPE" if pair_complete else "UNASSESSED",
                          reason=None if pair_complete else "INCOMPLETE_COMPONENT_IDENTITY",
                          source_record_refs=refs)

        finalize_check("duplicate_ingredient")
        ddi_components = {}
        for a, b in pairs:
            left, right = str(a['entry_version_id']), str(b['entry_version_id'])
            for lc, rc in product(resolved[left]['components'], resolved[right]['components']):
                component_result = {'component_refs': [{'entry_version_id': left, 'component_id': lc['id']},
                                                       {'entry_version_id': right, 'component_id': rc['id']}],
                                    'status': 'UNASSESSED', 'target_pair_results': [],
                                    'mapping_complete': lc['reliable'] and rc['reliable']}
                ddi_components[(left, right, lc['id'], rc['id'])] = component_result
                checks['ddi']['scope']['component_pair_results'].append(component_result)
        checks["ddi"]["execution"] = "RUNNING"
        # Each positive finding is committed before the next fallible dataset lookup.
        for index, (a, b) in enumerate(pairs):
            left, right = str(a["entry_version_id"]), str(b["entry_version_id"])
            l, r = resolved[left], resolved[right]
            output = checks["ddi"]["pair_results"][index]
            evaluated, positive, conflict = 0, False, False
            for lc, rc in product(l["components"], r["components"]):
                component_result = ddi_components[(left, right, lc['id'], rc['id'])]
                for lt, rt in product(sorted(lc["targets"]), sorted(rc["targets"])):
                    if lt == rt:
                        component_result['target_pair_results'].append({'target_ids': [lt, rt],
                            'status': 'DUPLICATE_RULE_ONLY'})
                        continue
                    looked = dataset.lookup(lt, rt)
                    component_result['target_pair_results'].append({'target_ids': [lt, rt], 'status': looked['status']})
                    statuses = {p['status'] for p in component_result['target_pair_results']}
                    component_result['status'] = ('CONFLICTING_SOURCE_RECORDS' if 'CONFLICTING_SOURCE_RECORDS' in statuses
                        else 'INTERACTION_DETECTED' if 'INTERACTION_DETECTED' in statuses else looked['status'])
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
                   'reminder_hold': hold,
                   "safe_to_take": None, "no_interactions": None, "requires_hcp_review": True,
                   "autonomous_prescribing": False, "automated_schedule_optimization": False}
