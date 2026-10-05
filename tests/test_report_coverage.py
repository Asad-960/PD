from copy import deepcopy
from types import SimpleNamespace
import pytest

from backend.catalogue.registry import drugs_by_id
from backend.evidence.patient_registry import PatientEvidenceRegistry
from backend.reports.coverage import build_organ_coverage
from backend.reports.safety import build_safety_alerts
from simulation.assessment_adapter import AssessmentTimelineAdapter
from backend.api import DemoService, RunRequest
from backend.reports.service import build_report
from backend.reports.pdf import render_pdf
from io import BytesIO
from pypdf import PdfReader


def test_coverage_separates_associations_rules_and_numerical_effects():
    drugs = drugs_by_id()
    rules = {rule.rule_id: rule.model_dump() for rule in PatientEvidenceRegistry().rules}
    coverage = build_organ_coverage(drugs, rules, AssessmentTimelineAdapter().capabilities())
    assert len(coverage) == 12
    assert all(len(cells) == 4 for cells in coverage.values())
    assert all(cell["numerical_status"] == "unsupported"
               for cells in coverage.values() for cell in cells.values())
    assert coverage["ibuprofen"]["renal"]["reviewed_rule_ids"] == ["RULE_NSAID_RENAL_HEMODYNAMIC"]
    assert coverage["ibuprofen"]["cardiovascular"]["associated"] is True
    assert coverage["ibuprofen"]["cardiovascular"]["reviewed_rule_ids"] == []
    assert coverage["ibuprofen"]["respiratory"]["associated"] is False
    assert coverage["morphine"]["hepatic"]["reviewed_rule_ids"] == ["RULE_OPIOID_HEPATIC_RESPIRATORY"]
    assert coverage["morphine"]["respiratory"]["reviewed_rule_ids"] == ["RULE_MORPHINE_RESPIRATORY"]
    assert coverage["saline"]["cardiovascular"]["reviewed_rule_ids"] == ["RULE_CHF_FLUID_OVERLOAD"]
    assert coverage["amlodipine"]["cardiovascular"]["reviewed_rule_ids"] == []


def test_administered_amount_is_not_classified_as_an_organ_metric():
    metrics = AssessmentTimelineAdapter().capabilities()["metrics"]
    assert all(row["domain"] == "administration" for row in metrics.values())


def test_model_metadata_alone_cannot_enable_numerical_organ_status():
    drugs = {"ibuprofen": drugs_by_id()["ibuprofen"]}
    declared = {"interventions": {"ibuprofen": {"numerical_effect": True,
        "numerical_model_id": "unverified-model", "numerical_organs": ["renal"]}}}
    coverage = build_organ_coverage(drugs, {}, declared)
    assert coverage["ibuprofen"]["renal"]["numerical_status"] == "unsupported"


def test_allergy_alert_is_patient_level_independent_of_target_order():
    intake = SimpleNamespace(patient=SimpleNamespace(allergies=["Ibuprofen"]))
    administration = {"event_id": "dose-1", "ingredient_id": "ibuprofen",
                      "simulation_time": 10.0}
    drugs = drugs_by_id()
    first = build_safety_alerts(intake, [administration], drugs)
    reordered = deepcopy(drugs)
    reordered["ibuprofen"]["target_organs"].reverse()
    second = build_safety_alerts(intake, [administration], reordered)
    assert first == second
    assert first == [{"event_id": "dose-1", "time": 10.0,
                      "ingredient_id": "ibuprofen", "reported_allergy": "Ibuprofen"}]


def patient_payload():
    return {
        "patient": {"name": "Fictional", "age": 39, "gender": "woman", "sex": None,
                    "mass_kg": 61, "allergies_status": "conditions", "allergies": ["ibuprofen"],
                    "current_medications_status": "none_known", "current_medications": []},
        "organs": {organ: {"status": "none_known", "conditions": []}
                   for organ in ("cardiovascular", "renal", "hepatic", "respiratory")},
        "blood_pressure": {"status": "unknown", "control": "unknown",
                           "systolic": None, "diastolic": None},
        "medications": [{"drug_id": "ibuprofen", "dose": 400, "unit": "mg", "route": "oral",
                         "time_seconds": 0, "duration_seconds": 0,
                         "repeat_count": 1, "interval_seconds": 0}],
        "measurements": [], "horizon_seconds": 10,
    }


def test_report_keeps_allergy_out_of_organ_findings(tmp_path, monkeypatch):
    payload = patient_payload()
    service = DemoService(str(tmp_path / "allergy.db"))
    try:
        run_id = service.start(RunRequest(intake=payload, assessment_mode="evidence_only"))
        service.workers[run_id]._thread.join(timeout=20)
        report = build_report(service.writer, run_id)
        assert len(report["safety_alerts"]) == 1
        assert report["safety_alerts"][0]["event_id"] == report["administrations"][0]["event_id"]
        assert not any(f["category"] == "reported_allergy_overlap"
                       for f in report["findings_timeline"])
        assert report["organ_coverage"]["ibuprofen"]["cardiovascular"]["associated"]
        assert report["pk_series"] == []  # no production parameter set is source-qualified
        pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(render_pdf(report))).pages)
        assert "Patient-level medication safety alert" in pdf_text
        report["pk_series"] = [{"drug_id": "ibuprofen", "name": "Ibuprofen", "unit": "mg/L",
            "c_max": 1, "t_max": 10, "therapeutic_min": 1, "therapeutic_max": 2,
            "points": [{"time": 0, "concentration": 0}, {"time": 10, "concentration": 1}]}]
        legacy_pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(render_pdf(report))).pages)
        assert "Illustrative concentration" not in legacy_pdf_text
        from backend.reports.pk import build_illustrative_pk
        import backend.reports.pdf as pdf_module
        report["pk_series"] = build_illustrative_pk(report["administrations"], drugs_by_id(),
            report["last_time"], report["last_time"], {"ibuprofen": {
                "model_id": "fictional_test", "parameter_source": "fictional test parameters",
                "ka": .0035, "ke": .00035, "vd_l": 10, "unit": "mg/L", "routes": ["oral"]}})
        markers = []
        original_circle = pdf_module.Circle
        def record_marker(x, y, radius, **kwargs):
            markers.append((x, y))
            return original_circle(x, y, radius, **kwargs)
        monkeypatch.setattr(pdf_module, "Circle", record_marker)
        pdf_module.render_pdf(report)
        assert markers and markers[0][0] > 400  # peak is near the right edge, not graph origin
    finally:
        service.close()


@pytest.mark.parametrize("drug_id,dose,unit,route,condition_organ,condition_id,expected", [
    ("amlodipine", 5, "mg", "oral", None, None, set()),
    ("ibuprofen", 400, "mg", "oral", "renal", "ckd", {"renal"}),
    ("morphine", 5, "mg", "intravenous", "hepatic", "cirrhosis", {"hepatic", "respiratory"}),
    ("saline", 500, "mL", "intravenous", "cardiovascular", "heart_failure", {"cardiovascular"}),
])
def test_golden_medicine_organ_cases(tmp_path, drug_id, dose, unit, route,
                                     condition_organ, condition_id, expected):
    payload = patient_payload()
    payload["patient"].update(allergies_status="none_known", allergies=[])
    payload["medications"][0].update(drug_id=drug_id, dose=dose, unit=unit, route=route)
    if condition_organ:
        payload["organs"][condition_organ] = {"status": "conditions", "conditions": [
            {"condition_id": condition_id, "severity": "unknown", "notes": ""}]}
    service = DemoService(str(tmp_path / f"{drug_id}.db"))
    try:
        run_id = service.start(RunRequest(intake=payload, assessment_mode="evidence_only"))
        service.workers[run_id]._thread.join(timeout=20)
        report = build_report(service.writer, run_id)
        actual = {organ for organ, response in report["visual_responses"].items()
                  if any(cue["kind"] == "source_linked_caution" for cue in response["cues"])}
        assert actual == expected
        assert report["pk_series"] == []
        assert all(cell["numerical_status"] == "unsupported"
                   for cell in report["organ_coverage"][drug_id].values())
    finally:
        service.close()
