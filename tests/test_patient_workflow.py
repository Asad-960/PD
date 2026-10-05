import time

import pytest
from fastapi.testclient import TestClient

from backend.api import DemoService, RunRequest, create_app


def intake():
    return {
        "patient": {"name": "Amina Test", "age": 39, "gender": "woman", "sex": None,
                    "mass_kg": 61.0, "allergies_status": "none_known", "allergies": [],
                    "current_medications_status": "none_known", "current_medications": []},
        "organs": {organ: {"status": "none_known", "conditions": []}
                   for organ in ("cardiovascular", "renal", "hepatic", "respiratory")},
        "blood_pressure": {"status": "unknown", "control": "unknown", "systolic": None,
                           "diastolic": None},
        "medications": [{"drug_id": "ibuprofen", "dose": 400.0, "unit": "mg", "route": "oral",
                         "time_seconds": 0.0, "duration_seconds": 0.0,
                         "repeat_count": 1, "interval_seconds": 0.0}],
        "measurements": [], "horizon_seconds": 60.0,
    }


def wait_for_run(service, run_id):
    service.workers[run_id]._thread.join(timeout=20)
    assert service.writer.get_run(run_id)["status"] == "completed"


def test_entered_profile_is_used_instead_of_fixed_demo_patient(tmp_path):
    service = DemoService(str(tmp_path / "patient.db"))
    try:
        run_id = service.start(RunRequest(intake=intake(), assessment_mode="evidence_only"))
        wait_for_run(service, run_id)
        run = service.writer.get_run(run_id)
        profile = service.writer.get_patient_profile(run["patient_id"])
        assert profile.age == 39
        assert profile.sex is None
        assert profile.mass_kg == 61.0
        assert profile.display_name == "Amina Test"
        assert profile.gender == "woman"
        unmodeled = [f for f in service.writer.get_findings_for_run(run_id) if f.coverage == "unsupported"]
        assert all("fixed illustrative constants" not in f.limitations for f in unmodeled)
    finally:
        service.close()


def test_preflight_rejects_prediction_and_lists_actual_coverage(tmp_path):
    with TestClient(create_app(str(tmp_path / "api.db"))) as client:
        response = client.post("/api/preflight", json=intake())
        assert response.status_code == 200
        result = response.json()
        assert result["can_run_evidence"]
        assert not result["can_run_numerical"]
        assert result["patient_prediction"] is False
        ibuprofen = result["medication_coverage"][0]
        assert ibuprofen["associated_organs"] == ["renal", "cardiovascular", "hepatic"]
        assert ibuprofen["reviewed_rule_organs"] == ["renal"]
        response = client.post("/api/runs", json={"intake": intake(), "assessment_mode": "numerical"})
        assert response.status_code == 422


@pytest.mark.parametrize("change", [
    {"dose": -1.0}, {"dose": True}, {"drug_id": "made_up_drug"},
    {"unit": "mL"}, {"route": "intravenous"}, {"time_seconds": 65.0},
    {"repeat_count": 2, "interval_seconds": 0.0},
])
def test_invalid_medication_rejected_before_run_creation(tmp_path, change):
    with TestClient(create_app(str(tmp_path / "invalid.db"))) as client:
        payload = intake()
        payload["medications"][0].update(change)
        response = client.post("/api/runs", json={"intake": payload, "assessment_mode": "evidence_only"})
        assert response.status_code == 422


def test_report_and_pdf_preserve_facts_and_never_invent_normal_labs(tmp_path):
    with TestClient(create_app(str(tmp_path / "report.db"))) as client:
        payload = intake()
        payload["patient"]["name"] = "<b>Amina & Test</b>"
        payload["patient"]["gender_detail"] = "Patient supplied description"
        payload["patient"]["sex"] = "female"
        payload["blood_pressure"]["notes"] = "History notes retained verbatim"
        payload["measurements"] = [{"name": "creatinine", "value": 1.23456789, "unit": "mg/dL"}]
        payload["organs"]["renal"] = {"status": "conditions", "conditions": [
            {"condition_id": "ckd", "severity": "unknown", "notes": ""}]}
        response = client.post("/api/runs", json={"intake": payload, "assessment_mode": "evidence_only"})
        assert response.status_code == 201, response.text
        run_id = response.json()["run_id"]
        wait_for_run(client.app.state.service, run_id)
        report_response = client.get(f"/api/runs/{run_id}/report")
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["patient"]["age"] == 39
        assert report["patient"]["name"] == "<b>Amina & Test</b>"
        assert report["measurements"][0]["value"] == 1.23456789
        assert len(report["measurements"]) == 1
        assert report["clinical_validation"] is False
        assert len(report["organs"]) == 4
        assert any(f["coverage"] == "evidence_only" for f in report["organs"]["renal"]["findings"])
        assert report["visual_responses"]["renal"]["pattern"] == "structural_change"
        assert report["visual_responses"]["renal"]["safety_signal"] == "review_required"
        assert [cue["kind"] for cue in report["visual_responses"]["renal"]["cues"]] == [
            "exposure_only", "source_linked_caution"]
        assert report["visual_responses"]["cardiovascular"]["safety_signal"] == "no_flag_in_limited_checks"
        assert all(q["name"].startswith("administered_") for s in report["snapshots"] for q in s["quantities"])
        pdf = client.get(f"/api/runs/{run_id}/report.pdf?cursor={report['cursor']}")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")
        from io import BytesIO
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        assert "Amina & Test" in text
        assert "400" in text
        assert report["report_id"] in text
        assert "Patient supplied description" in text
        assert "History notes retained verbatim" in text
        assert "Physiological sex parameter: female" in text
        assert "1.23456789" in text


def test_single_gender_selection_can_supply_engine_sex(tmp_path):
    payload = intake()
    payload["patient"].update(gender="female", sex="female")
    with TestClient(create_app(str(tmp_path / "gender.db"))) as client:
        response = client.post("/api/preflight", json=payload)
        assert response.status_code == 200


def test_future_exposure_does_not_trigger_current_warning(tmp_path):
    from backend.intake import prepare_intake
    from backend.schemas.intake import PatientIntake
    from simulation.assessment_adapter import AssessmentTimelineAdapter
    from backend.council import OrganCouncil
    payload = intake()
    payload["organs"]["renal"] = {"status": "conditions", "conditions": [
        {"condition_id": "ckd", "severity": "unknown", "notes": ""}]}
    payload["medications"][0]["time_seconds"] = 30.0
    profile, config, actions = prepare_intake(PatientIntake.model_validate(payload), "future")
    engine = AssessmentTimelineAdapter()
    engine.initialize(profile.model_dump())
    from backend.schemas.domain import PhysiologySnapshot
    snapshot = PhysiologySnapshot.model_validate({**engine.snapshot(), "run_id": "future"})
    drafts = OrganCouncil().evaluate(profile, snapshot, actions)
    assert not any(f.rule_id == "RULE_NSAID_RENAL_HEMODYNAMIC" for f in drafts)


def test_equivalent_units_and_repeat_schedule_have_same_administered_amount():
    from backend.intake import prepare_intake
    from backend.schemas.intake import PatientIntake
    from simulation.assessment_adapter import AssessmentTimelineAdapter
    for dose, unit in [(400.0, "mg"), (0.4, "g"), (400000.0, "mcg")]:
        payload = intake()
        payload["medications"][0].update(dose=dose, unit=unit, repeat_count=2, interval_seconds=30.0)
        profile, config, actions = prepare_intake(PatientIntake.model_validate(payload), "units")
        assert [a.simulation_time for a in actions] == [0.0, 30.0]
        engine = AssessmentTimelineAdapter()
        engine.initialize(profile.model_dump())
        for action in actions:
            engine.advance(action.simulation_time - engine.simulation_time)
            assert engine.apply_event(action.model_dump())
        assert engine.snapshot()["quantities"]["administered_ibuprofen"]["value"] == pytest.approx(800.0)


def test_pdf_distinguishes_duplicate_medication_rows_and_normalized_units(tmp_path):
    from io import BytesIO
    from pypdf import PdfReader
    from backend.reports.pdf import render_pdf
    from backend.reports.service import build_report

    payload = intake()
    payload["medications"].append({**payload["medications"][0], "dose": 0.2, "unit": "g", "time_seconds": 20.0})
    service = DemoService(str(tmp_path / "duplicate-medication.db"))
    try:
        run_id = service.start(RunRequest(intake=payload, assessment_mode="evidence_only"))
        wait_for_run(service, run_id)
        text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(render_pdf(build_report(service.writer, run_id)))).pages)
        assert "400 mg" in text
        assert "0.2 g" in text
        assert "200 mg" in text
        assert "600 mg" not in text
    finally:
        service.close()


def test_historical_report_uses_submission_catalogue_and_evidence(tmp_path, monkeypatch):
    from backend.reports import service as reports
    service = DemoService(str(tmp_path / "history.db"))
    try:
        payload = intake()
        payload["organs"]["renal"] = {"status": "conditions", "conditions": [
            {"condition_id": "ckd", "severity": "unknown"}]}
        run_id = service.start(RunRequest(intake=payload, assessment_mode="evidence_only"))
        wait_for_run(service, run_id)
        monkeypatch.setattr(reports, "conditions_by_id", lambda: {})
        monkeypatch.setattr(reports, "drugs_by_id", lambda: {})
        monkeypatch.setattr(reports, "preflight", lambda _: {"errors": ["changed registry"]})
        report = reports.build_report(service.writer, run_id)
        assert report["organs"]["renal"]["conditions"][0]["name"]
        assert report["scope"]["errors"] == []
        assert report["assessment_basis_pinned"] is True
        assert report["intake"]["patient"]["age"] == 39
        finding = next(f for f in report["findings_timeline"] if f["rule_id"] == "RULE_NSAID_RENAL_HEMODYNAMIC")
        assert "filtration" in finding["explanation"]
        assert finding["sources"][0]["source_id"] == "NIDDK_MEDICINE"
    finally:
        service.close()


def test_report_records_exact_repeats_and_cursor_isolation(tmp_path):
    from backend.reports.service import build_report
    service = DemoService(str(tmp_path / "repeat.db"))
    try:
        payload = intake()
        payload["medications"][0].update(time_seconds=10.0, repeat_count=2, interval_seconds=20.0)
        run_id = service.start(RunRequest(intake=payload, assessment_mode="evidence_only"))
        wait_for_run(service, run_id)
        report = build_report(service.writer, run_id)
        assert [a["simulation_time"] for a in report["administrations"]] == [10.0, 30.0]
        assert report["administration_series"][0]["points"][-1]["value"] == 800.0
        first_applied = next(e for e in service.writer.get_events_after(run_id, -1, 500) if e.event_type == "INTERVENTION_APPLIED")
        partial = build_report(service.writer, run_id, first_applied.sequence - 1)
        assert partial["administrations"] == []
        assert all(not response["cues"] for response in partial["visual_responses"].values())
        assert partial["pk_series"] == []
        assert not partial["is_final"]
        assert partial["administration_series"][0]["points"][-1]["value"] == 0
        assert build_report(service.writer, run_id, partial["cursor"]) == partial
    finally:
        service.close()


def test_identical_concurrent_requests_launch_one_worker(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from simulation.worker import SimulationWorker
    calls = []
    original = SimulationWorker.start_in_background

    def start(worker):
        calls.append(worker.run_id)
        return original(worker)

    monkeypatch.setattr(SimulationWorker, "start_in_background", start)
    service = DemoService(str(tmp_path / "concurrent.db"))
    try:
        request = RunRequest(intake=intake(), assessment_mode="evidence_only", request_id="a" * 32)
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(service.start, [request] * 4))
        assert len(set(ids)) == 1
        assert len(calls) == 1
        wait_for_run(service, ids[0])
        changed = intake()
        changed["patient"]["age"] = 40
        with pytest.raises(ValueError, match="different patient intake"):
            service.start(RunRequest(intake=changed, assessment_mode="evidence_only", request_id="a" * 32))
    finally:
        service.close()
