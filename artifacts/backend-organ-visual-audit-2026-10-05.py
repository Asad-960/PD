"""Focused, fictional-case audit of medication-to-organ visual report behavior."""
import json
import tempfile
from pathlib import Path

from backend.api import DemoService, RunRequest
from backend.catalogue.registry import drugs_by_id
from backend.evidence.patient_registry import PatientEvidenceRegistry
from backend.reports.service import build_report


def intake(drug_id, dose, unit, route, organ=None, condition=None):
    organs = {key: {"status": "none_known", "conditions": []}
              for key in ("cardiovascular", "renal", "hepatic", "respiratory")}
    if organ and condition:
        organs[organ] = {"status": "conditions", "conditions": [
            {"condition_id": condition, "severity": "unknown", "notes": ""}]}
    return {
        "patient": {"name": "Fictional Audit", "age": 39, "gender": "woman", "sex": None,
                    "mass_kg": 61.0, "allergies_status": "none_known", "allergies": [],
                    "current_medications_status": "none_known", "current_medications": []},
        "organs": organs,
        "blood_pressure": {"status": "unknown", "control": "unknown",
                           "systolic": None, "diastolic": None},
        "medications": [{"drug_id": drug_id, "dose": dose, "unit": unit,
                         "route": route, "time_seconds": 0, "duration_seconds": 0,
                         "repeat_count": 1, "interval_seconds": 0}],
        "measurements": [], "horizon_seconds": 60,
    }


def run_case(database_path, payload):
    service = DemoService(str(database_path))
    try:
        run_id = service.start(RunRequest(intake=payload, assessment_mode="evidence_only"))
        service.workers[run_id]._thread.join(timeout=20)
        assert service.writer.get_run(run_id)["status"] == "completed"
        report = build_report(service.writer, run_id)
        return {
            "cues": {organ: row["cues"] for organ, row in report["visual_responses"].items()},
            "findings": [{"organ": finding["organ"], "rule_id": finding["rule_id"],
                          "time": finding["simulation_time"],
                          "causal_event_ids": finding.get("causal_event_ids", [])}
                         for finding in report["findings_timeline"]
                         if finding["coverage"] == "evidence_only"],
            "last_time": report["last_time"],
        }
    finally:
        service.close()


if __name__ == "__main__":
    drugs = drugs_by_id()
    rules = PatientEvidenceRegistry().rules
    matrix = {
        key: {"target_organs": drug["target_organs"],
              "evidence_available": drug["evidence_available"],
              "reviewed_rule_organs": sorted({rule.target_organ for rule in rules
                                              if rule.ingredient_or_class == key})}
        for key, drug in drugs.items()
    }
    with tempfile.TemporaryDirectory(prefix="pdtt-organ-audit-", dir=Path(__file__).parent) as folder:
        path = Path(folder)
        output = {
            "catalogue_count": len(drugs),
            "reviewed_rule_count": len(rules),
            "matrix": matrix,
            "ibuprofen_ckd": run_case(path / "ibuprofen.db", intake(
                "ibuprofen", 400, "mg", "oral", "renal", "ckd")),
            "amlodipine": run_case(path / "amlodipine.db", intake(
                "amlodipine", 5, "mg", "oral")),
        }
    out = Path(__file__).with_suffix(".json")
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"catalogue_count": output["catalogue_count"],
                      "reviewed_rule_count": output["reviewed_rule_count"],
                      "ibuprofen_cue_kinds": {organ: [cue["kind"] for cue in cues]
                           for organ, cues in output["ibuprofen_ckd"]["cues"].items()},
                      "ibuprofen_first_finding_time": output["ibuprofen_ckd"]["findings"][0]["time"],
                      "amlodipine_cue_kinds": {organ: [cue["kind"] for cue in cues]
                           for organ, cues in output["amlodipine"]["cues"].items()}}, indent=2))
