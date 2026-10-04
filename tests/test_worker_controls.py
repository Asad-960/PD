"""Worker ownership, action retry and safe-boundary command behavior."""
import threading
import time

import pytest

from backend.database.writer import PersistenceWriter
from backend.schemas.domain import PatientProfile, SimulationConfig, Intervention
from simulation.adapter import IllustrativeEngineAdapter
from simulation.worker import SimulationWorker


@pytest.fixture
def writer():
    w = PersistenceWriter(":memory:")
    try:
        yield w
    finally:
        w.close()


def action(event_id, key="same", dose=500):
    return Intervention(event_id=event_id, idempotency_key=key,
                        ingredient_id="saline", dose=dose, unit="mL",
                        route="intravenous", simulation_time=0)


def worker(writer, interventions=(), engine=None, run_id="r", horizon=5):
    return SimulationWorker(run_id,
        PatientProfile(patient_id="p", age=45, sex="male", mass_kg=70),
        SimulationConfig(run_id=run_id, profile_hash="unverified", horizon_seconds=horizon),
        list(interventions), writer, engine_adapter=engine)


def test_same_key_exact_retry_applies_once_and_conflict_is_rejected(writer):
    engine = IllustrativeEngineAdapter()
    owner = worker(writer, [action("first"), action("retry")], engine=engine)
    owner.run()
    assert len(engine.active_events) == 1
    assert len(writer.get_interventions_for_run("r")) == 1
    with pytest.raises(ValueError, match="idempotency"):
        worker(writer, [action("first"), action("conflict", dose=700)])


def test_duplicate_background_start_reuses_one_thread(writer):
    entered, release = threading.Event(), threading.Event()

    class Blocking(IllustrativeEngineAdapter):
        def initialize(self, profile, assumptions=None):
            entered.set()
            assert release.wait(2)
            return super().initialize(profile, assumptions)

    owner = worker(writer, engine=Blocking())
    thread = owner.start_in_background()
    try:
        assert entered.wait(2)
        assert owner.start_in_background() is thread
    finally:
        release.set()
        owner.cancel()
        thread.join(2)
    assert not thread.is_alive()


def test_prestart_pause_and_resume_get_ordered_persisted_acknowledgements(writer):
    owner = worker(writer)
    owner.pause()
    owner.resume()
    owner.run()
    types = [event.event_type for event in writer.get_events_after("r")]
    assert types.index("RUN_STARTED") < types.index("RUN_PAUSED") < types.index("RUN_RESUMED")
    assert writer.get_run("r")["status"] == "completed"


def test_pause_ack_occurs_after_in_flight_advance_and_freezes_clock(writer):
    entered, release = threading.Event(), threading.Event()

    class Blocking(IllustrativeEngineAdapter):
        def advance(self, delta):
            entered.set()
            assert release.wait(2)
            return super().advance(delta)

    owner = worker(writer, engine=Blocking())
    thread = owner.start_in_background()
    try:
        assert entered.wait(2)
        owner.pause()
        release.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and writer.get_run("r")["status"] != "paused":
            time.sleep(0.005)
        assert writer.get_run("r")["status"] == "paused"
        before = owner.engine.simulation_time
        time.sleep(0.02)
        assert owner.engine.simulation_time == before
        owner.resume()
        thread.join(2)
        assert not thread.is_alive()
    finally:
        owner.cancel()
        release.set()
        thread.join(2)


def test_cancel_after_last_advance_cannot_complete(writer):
    entered, release = threading.Event(), threading.Event()

    class Blocking(IllustrativeEngineAdapter):
        def advance(self, delta):
            entered.set()
            assert release.wait(2)
            return super().advance(delta)

    owner = worker(writer, engine=Blocking(), horizon=1)
    thread = owner.start_in_background()
    try:
        assert entered.wait(2)
        owner.cancel()
        release.set()
        thread.join(2)
        assert not thread.is_alive()
        assert writer.get_run("r")["status"] == "cancelled"
        assert not any(e.event_type == "RUN_COMPLETED" for e in writer.get_events_after("r"))
    finally:
        release.set()
        thread.join(2)
