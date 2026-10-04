"""The worker must persist truthful identity and reject unsuccessful engine calls."""
import pytest
from backend.database.writer import PersistenceWriter
from backend.schemas.domain import PatientProfile, SimulationConfig, Intervention, QuantitySnapshot
from simulation.adapter import IllustrativeEngineAdapter
from simulation.worker import SimulationWorker


@pytest.fixture
def writer():
    result = PersistenceWriter(":memory:")
    try:
        yield result
    finally:
        result.close()


def worker(writer, engine=None, interventions=None, config=None):
    return SimulationWorker(
        "boundary", PatientProfile(patient_id="p", age=45, sex="male", mass_kg=70),
        config or SimulationConfig(run_id="boundary", profile_hash="baseline", horizon_seconds=10),
        interventions or [], writer, engine_adapter=engine,
    )


def saline(ingredient="saline"):
    return Intervention(event_id="s", ingredient_id=ingredient, dose=500, unit="mL",
                        route="intravenous", simulation_time=0, idempotency_key="s")


def test_default_quantity_cannot_claim_unverified_pulse_output():
    q = QuantitySnapshot(value=90, unit="mmHg")
    assert q.source == "unverified"
    assert q.capability == "unsupported"


def test_persisted_config_identifies_actual_adapter(writer):
    owner = worker(writer)
    owner.run()
    stored = writer.get_run("boundary")["config"]
    assert stored["engine_name"] == "PDTT Illustrative Fluid Bookkeeping"
    assert stored["engine_version"] == "0.2.0"
    assert stored["assumptions"]["execution_mode"] == "ILLUSTRATIVE"
    assert writer.get_latest_snapshot("boundary").quantities["heart_rate"].capability == "illustrative"


def test_explicit_request_for_other_engine_cannot_silently_fall_back(writer):
    config = SimulationConfig(run_id="boundary", profile_hash="baseline",
                              engine_name="Kitware Pulse", engine_version="4.4")
    with pytest.raises(ValueError, match="engine"):
        worker(writer, config=config)
    assert writer.get_run("boundary") is None


def test_rejected_initialization_is_failed_not_successful(writer):
    class Rejecting(IllustrativeEngineAdapter):
        def initialize(self, *args):
            super().initialize(*args)
            return False
    owner = worker(writer, engine=Rejecting())
    with pytest.raises(RuntimeError, match="initialization"):
        owner.run()
    assert writer.get_run("boundary")["status"] == "failed"
    assert writer.get_latest_snapshot("boundary") is None


def test_rejected_advance_cannot_be_recorded_as_completion(writer):
    class Rejecting(IllustrativeEngineAdapter):
        def advance(self, delta):
            return False
    with pytest.raises(RuntimeError, match="advance"):
        worker(writer, engine=Rejecting()).run()
    assert writer.get_run("boundary")["status"] == "failed"
    assert writer.get_latest_snapshot("boundary").simulation_time == 0


def test_rejected_action_cannot_emit_applied_event(writer):
    class Rejecting(IllustrativeEngineAdapter):
        def apply_event(self, event):
            return False
    with pytest.raises(RuntimeError, match="action"):
        worker(writer, engine=Rejecting(), interventions=[saline()]).run()
    assert writer.get_run("boundary")["status"] == "failed"
    assert not any(e.event_type == "INTERVENTION_APPLIED" for e in writer.get_events_after("boundary"))


def test_unsupported_action_is_blocked_by_preflight(writer):
    with pytest.raises(ValueError, match="unsupported"):
        worker(writer, interventions=[saline("norepinephrine")]).run()
    assert writer.get_latest_snapshot("boundary") is None
    assert writer.get_run("boundary")["status"] == "failed"


def test_numerical_invalidity_survives_boundary_and_fails_run(writer):
    class Invalid(IllustrativeEngineAdapter):
        def snapshot(self):
            raw = super().snapshot()
            raw["is_valid"] = False
            raw["numerical_error_code"] = "INVALID_ILLUSTRATIVE_STATE"
            return raw
    with pytest.raises(RuntimeError, match="invalid"):
        worker(writer, engine=Invalid()).run()
    assert writer.get_latest_snapshot("boundary") is None
    assert writer.get_run("boundary")["status"] == "failed"
