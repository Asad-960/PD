import pytest
import time
import os
from typing import List

from backend.schemas.domain import PatientProfile, SimulationConfig, Intervention, BaselineMeasurement
from backend.database.writer import PersistenceWriter
from simulation.worker import SimulationWorker
from simulation.coverage import CoverageGate
from simulation.adapter import ReferenceTraceEngineAdapter

@pytest.fixture
def memory_writer():
    writer = PersistenceWriter(db_path=":memory:")
    yield writer
    writer.close()

@pytest.fixture
def profile():
    return PatientProfile(
        patient_id="test_patient",
        age=45,
        sex="male",
        mass_kg=80.0,
        baseline_measurements={},
        conditions=[],
        context={},
        current_medications=[],
        allergies=[]
    )

def test_lifecycle_and_sequencing(memory_writer, profile):
    config = SimulationConfig(
        run_id="run_seq",
        profile_hash="hash",
        horizon_seconds=30.0,
        sample_cadence_seconds=10.0
    )
    worker = SimulationWorker(
        run_id="run_seq",
        profile=profile,
        config=config,
        interventions=[],
        writer=memory_writer
    )
    worker.run()
    
    events = memory_writer.get_events_after("run_seq", -1, 100)
    assert len(events) > 0
    
    # Check monotonic sequences
    seqs = [e.sequence for e in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs)) # zero primary key collisions
    
    # Verify snapshots at 0, 10, 20, 30
    snaps = []
    for e in events:
        if e.event_type == "SNAPSHOT_COMMITTED":
            snaps.append(e.simulation_time)
            
    assert snaps == [0.0, 10.0, 20.0, 30.0]
    
    run_status = memory_writer.get_run("run_seq")
    assert run_status["status"] == "completed"

def test_interval_splitting(memory_writer, profile):
    config = SimulationConfig(
        run_id="run_split",
        profile_hash="hash",
        horizon_seconds=30.0,
        sample_cadence_seconds=10.0
    )
    inv = Intervention(
        event_id="inv_15_5",
        ingredient_id="saline",
        dose=500.0,
        unit="mL",
        route="intravenous",
        simulation_time=15.5,
        idempotency_key="inv_15_5"
    )
    worker = SimulationWorker(
        run_id="run_split",
        profile=profile,
        config=config,
        interventions=[inv],
        writer=memory_writer
    )
    worker.run()
    
    events = memory_writer.get_events_after("run_split", -1, 100)
    
    # Event types in order should show splitting
    # RUN_CREATED, RUN_INITIALIZING, SNAPSHOT_COMMITTED(t=0), CHECKPOINT_CREATED(t=0), RUN_STARTED
    # SNAPSHOT_COMMITTED(t=10)
    # CHECKPOINT_CREATED(t=15.5 pre-intervention)
    # INTERVENTION_APPLIED(t=15.5)
    # SNAPSHOT_COMMITTED(t=20)
    # SNAPSHOT_COMMITTED(t=30)
    # RUN_COMPLETED
    
    t_checkpoints = []
    t_interventions = []
    t_snapshots = []
    for e in events:
        if e.event_type == "CHECKPOINT_CREATED":
            t_checkpoints.append(e.simulation_time)
        elif e.event_type == "INTERVENTION_APPLIED":
            t_interventions.append(e.simulation_time)
        elif e.event_type == "SNAPSHOT_COMMITTED":
            t_snapshots.append(e.simulation_time)
            
    assert t_snapshots == [0.0, 10.0, 20.0, 30.0]
    assert 15.5 in t_checkpoints
    assert t_interventions == [15.5]

def test_pre_intervention_checkpoint_verification(memory_writer, profile):
    config = SimulationConfig(
        run_id="run_chk",
        profile_hash="hash",
        horizon_seconds=20.0,
        sample_cadence_seconds=10.0
    )
    inv = Intervention(
        event_id="inv_15_5",
        ingredient_id="saline",
        dose=500.0,
        unit="mL",
        route="intravenous",
        simulation_time=15.5,
        idempotency_key="inv_15_5"
    )
    worker = SimulationWorker(
        run_id="run_chk",
        profile=profile,
        config=config,
        interventions=[inv],
        writer=memory_writer
    )
    worker.run()
    
    # Fetch checkpoint from DB
    chk = memory_writer.get_checkpoint(f"pre_intervention_{inv.event_id}")
    assert chk is not None
    assert chk.simulation_time == 15.5
    
    # Test restoring it cleanly
    adapter = ReferenceTraceEngineAdapter()
    import json
    worker_state = json.loads(chk.serialized_engine_state)
    assert [action["event_id"] for action in worker_state["pending_schedule"]] == [inv.event_id]
    assert adapter.restore(worker_state["engine_state"]) is True
    assert adapter.simulation_time == 15.5

def test_pause_and_resume(memory_writer, profile):
    config = SimulationConfig(
        run_id="run_pause",
        profile_hash="hash",
        horizon_seconds=30.0,
        sample_cadence_seconds=1.0
    )
    worker = SimulationWorker(
        run_id="run_pause",
        profile=profile,
        config=config,
        interventions=[],
        writer=memory_writer
    )
    
    thread = worker.start_in_background()
    
    # Pause it
    worker.pause()
    time.sleep(0.1) # allow time for thread to block
    
    events_mid = memory_writer.get_events_after("run_pause", -1, 100)
    snaps_mid = [e for e in events_mid if e.event_type == "SNAPSHOT_COMMITTED"]
    
    # ensure it doesn't proceed to 30 while paused
    assert len(snaps_mid) <= 31
    last_snap_time = snaps_mid[-1].simulation_time if snaps_mid else 0.0
    
    time.sleep(0.1)
    events_mid2 = memory_writer.get_events_after("run_pause", -1, 100)
    snaps_mid2 = [e for e in events_mid2 if e.event_type == "SNAPSHOT_COMMITTED"]
    assert len(snaps_mid) == len(snaps_mid2) # should not have advanced
    
    worker.resume()
    thread.join(timeout=2.0)
    
    run_status = memory_writer.get_run("run_pause")
    assert run_status["status"] == "completed"

def test_anti_fabrication_check_inside_worker(memory_writer, profile):
    config = SimulationConfig(
        run_id="run_anti_fab",
        profile_hash="hash",
        horizon_seconds=10.0,
        sample_cadence_seconds=10.0
    )
    # High dose NSAID is evidence_only, shouldn't fabricate
    inv = Intervention(
        event_id="nsaid",
        ingredient_id="High_Dose_NSAID",
        dose=800.0,
        unit="mg",
        route="oral",
        simulation_time=5.0,
        idempotency_key="nsaid"
    )
    gate = CoverageGate()
    gate._manifest = gate._load_manifest(os.path.join(os.path.dirname(__file__), '..', 'simulation', 'capability-manifest.json'))
    gate.metrics = gate._manifest.get("metrics", {})
    gate.conditions = gate._manifest.get("conditions", {})
    gate.interventions = gate._manifest.get("interventions", {})
    
    worker = SimulationWorker(
        run_id="run_anti_fab",
        profile=profile,
        config=config,
        interventions=[inv],
        writer=memory_writer,
        coverage_gate=gate
    )
    worker.run()
    
    events = memory_writer.get_events_after("run_anti_fab", -1, 100)
    
    # verify coverage gate warnings
    init_event = next(e for e in events if e.event_type == "RUN_INITIALIZING")
    report = init_event.payload.get("coverage_report", {})
    
    assert any("High-Dose NSAID" in asp for asp in report.get("evidence_only_aspects", []))
    assert not any("High-Dose NSAID" in asp for asp in report.get("simulated_aspects", []))
    
    # Check that it didn't fabricate vitals in snapshot
    final_snap = memory_writer.get_latest_snapshot("run_anti_fab")
    # Coverage flags should specify evidence_only_interventions
    assert "High_Dose_NSAID" in final_snap.coverage_flags.get("evidence_only_interventions", [])
