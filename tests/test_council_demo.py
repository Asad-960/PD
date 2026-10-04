from backend.api import DemoService, RunRequest
from backend.council import OrganCouncil
from backend.schemas.domain import PatientProfile, PhysiologySnapshot, Intervention


def test_council_is_read_only_and_reports_four_observers():
    profile = PatientProfile(patient_id="synthetic", age=55, sex="female", mass_kg=70.0)
    snapshot = PhysiologySnapshot(
        run_id="council_run", sequence=9, simulation_time=10.0,
        quantities={"total_fluid_volume": {"value": 41.0, "unit": "L",
                    "source": "illustration", "capability": "illustrative"}},
    )
    original = snapshot.model_dump_json()
    drafts = OrganCouncil().evaluate(profile, snapshot, [])
    assert len(drafts) == 4
    assert {item.organ for item in drafts} == {
        "renal", "cardiovascular", "hepatic", "respiratory"}
    assert all(item.source_snapshot_sequence == 9 and
               item.coverage == "unsupported" for item in drafts)
    assert snapshot.model_dump_json() == original


def test_two_drug_demo_has_independent_findings_and_contiguous_replay(tmp_path):
    service = DemoService(str(tmp_path / "demo.db"))
    try:
        run_id = service.start(RunRequest(
            preset="two_drug_review", horizon_seconds=25,
            sample_cadence_seconds=5, diabetes=True))
        worker = service.workers[run_id]
        worker._thread.join(timeout=20)
        assert not worker._thread.is_alive()
        assert service.writer.get_run(run_id)["status"] == "completed"
        events = service.writer.get_events_after(run_id, -1, 500)
        assert [item.sequence for item in events] == list(range(1, len(events) + 1))
        findings = service.writer.get_findings_for_run(run_id)
        assert any(item.organ == "renal" and item.coverage == "evidence_only" for item in findings)
        assert any(item.organ == "hepatic" and item.coverage == "evidence_only" for item in findings)
        assert not any(item.category == "drug_interaction_prediction" for item in findings)
        latest = service.writer.get_latest_snapshot(run_id)
        assert latest.quantities["total_fluid_volume"].value == 42.0
        assert all(item.coverage_flags["patient_prediction"] is False
                   for item in [latest])
    finally:
        service.close()
