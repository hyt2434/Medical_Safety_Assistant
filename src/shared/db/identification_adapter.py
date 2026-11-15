"""Core REF lookup plus an explicit crosswalk adapter for existing Module 2 references."""
from copy import deepcopy
from psycopg.types.json import Jsonb


def text_key(value):
    return "".join(str(value or "").casefold().split())


class CoreMedicationReference:
    def __init__(self, repo, dataset_build):
        self.repo, self.build = repo, dataset_build
        if not repo._one("SELECT msa.published(%s) AS ok", (dataset_build,))["ok"]:
            raise ValueError("Reference build is not published")

    def lookup(self, fields):
        name = fields.get("name_raw") or fields.get("brand_name")
        if not name:
            return {"candidates": [], "complete_identity": False, "limitations": ["Medication name is missing"]}
        rows = self.repo._all("""SELECT * FROM msa_ref.medications
            WHERE dataset_build=%s AND lower(brand_name)=lower(%s) ORDER BY id""", (self.build, name))
        candidates, limitations = [], []
        for row in rows:
            details = row["product_details"]
            missing = []
            qualifiers = {"strength_raw": details["source_identity_definition"].get("strength"),
                          "dosage_form_raw": row["dosage_form"], "route_raw": row["route"],
                          "registration_token": details.get("registration_token"), "manufacturer": row["manufacturer"]}
            incompatible = False
            for key, actual in qualifiers.items():
                if fields.get(key):
                    if not actual:
                        missing.append(key)
                    elif text_key(fields[key]) != text_key(actual):
                        incompatible = True
            if not incompatible:
                candidates.append({"id": row["id"], "source_medication_id": row["source_medication_id"],
                                   "source_locator": row["source_locator"], "missing_qualifiers": missing})
        essential_uncertainty = set(fields.get("uncertain_fields", [])) & {
            "name_raw", "strength_raw", "dosage_form_raw", "route_raw", "registration_token", "manufacturer"}
        if essential_uncertainty:
            limitations.append("Uncertain identity fields: " + ", ".join(sorted(essential_uncertainty)))
        complete = len(candidates) == 1 and not candidates[0]["missing_qualifiers"] and not essential_uncertainty
        return {"candidates": candidates, "complete_identity": complete, "limitations": limitations}


def run_identification(repo, entry_id, *, dataset_build=None, reference=None, accepted_source_crosswalk=None,
                       matcher_version="core-module2-adapter-v4"):
    entry = repo._owned("medication_entry_versions", entry_id)
    if entry["confirmed_at"] is None:
        raise ValueError("Module 2 handoff requires exact owner-confirmed input")
    basis = {"schema": "match-evidence.v4", "method": matcher_version, "qualifiers": deepcopy(entry["medication_fields"]),
             "external_candidates": [], "candidate_evidence": [], "outcome_reason": None, "limitations": []}
    product, candidates = None, []
    try:
        if reference is None:
            if dataset_build is None:
                raise ValueError("A pinned dataset_build is required")
            result = CoreMedicationReference(repo, dataset_build).lookup(entry["medication_fields"])
            candidates = [c["id"] for c in result["candidates"]]
            basis["candidate_evidence"] = [{"product_id": str(c["id"]), "source_medication_id": c["source_medication_id"],
                                           "source_locator": c["source_locator"], "missing_qualifiers": c["missing_qualifiers"]}
                                          for c in result["candidates"]]
            basis["limitations"] = result["limitations"]
            if result["complete_identity"]:
                product = candidates[0]
        else:
            result = reference.lookup(entry["medication_fields"])
            basis["external_candidates"] = deepcopy(result.get("candidates", []))
            crosswalk = accepted_source_crosswalk or {}
            missing = []
            for candidate in result.get("candidates", []):
                handle = candidate.get("candidate_key")
                core_id = crosswalk.get(handle)
                if core_id is None:
                    missing.append(handle)
                elif core_id not in candidates:
                    candidates.append(core_id)
            if missing:
                basis["limitations"].append("External handles lack a source-supported Core crosswalk")
            if result.get("identification_status") == "VERIFIED" and len(candidates) == 1 and not missing:
                product = candidates[0]
                selected = repo._one("SELECT dataset_build FROM msa_ref.medications WHERE id=%s", (product,))
                dataset_build = selected["dataset_build"] if selected else dataset_build
        status = "SELECTED" if product else "AMBIGUOUS" if candidates or basis["external_candidates"] else "NO_MATCH"
    except Exception as exc:
        result, status = None, "FAILED"
        basis["outcome_reason"] = type(exc).__name__ + ": " + str(exc)
    match = repo.record_match(entry_id, status, product=product, candidates=candidates, reference_build=dataset_build,
                              matcher_version=matcher_version, evidence=basis, confidence=None)
    return match, result
