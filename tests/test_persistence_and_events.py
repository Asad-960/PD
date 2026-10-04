"""
Tests for Gate 4: SQLite Persistence and Append-Only Event System.
Verifies:
- WAL mode pragma application
- Thread-safe single persistence writer under rapid / concurrent streaming
- Monotonically sequenced event logging and catch-up queries (get_events_after)
- Checkpoint persistence and exact retrieval
- Foreign key enforcement and domain model integrity
"""

import concurrent.futures
import sqlite3
import pytest

from backend.database.writer import PersistenceWriter, canonical_profile_hash
from backend.events.types import (
    EventType,
    create_run_created_event,
    create_snapshot_event,
    create_finding_event,
    create_checkpoint_event,
)
from backend.schemas.domain import (
    PatientProfile,
    SimulationConfig,
    PhysiologySnapshot,
    AgentFinding,
    Checkpoint,
    ReviewRecord,
)


@pytest.fixture
def temp_writer(tmp_path):
    db_file = str(tmp_path / "test_pdtt.db")
    writer = PersistenceWriter(db_path=db_file)
    yield writer
    writer.close()


@pytest.fixture
def sample_profile():
    return PatientProfile(
        patient_id="patient_test_01",
        age=58,
        sex="male",
        mass_kg=74.0,
        conditions=["ChronicRenalStenosis", "EssentialHypertension"],
        context={"diabetes": True}
    )


@pytest.fixture
def sample_config(sample_profile):
    return SimulationConfig(
        run_id="run_test_01",
        engine_name="Pulse Physiology Engine",
        engine_version="4.4.0",
        profile_hash=canonical_profile_hash(sample_profile),
        horizon_seconds=300.0,
        sample_cadence_seconds=1.0
    )


def test_sqlite_wal_mode_and_pragmas(tmp_path):
    """Verify that file-backed SQLite properly activates WAL mode and pragmas."""
    db_file = str(tmp_path / "wal_test.db")
    writer = PersistenceWriter(db_path=db_file)

    cursor = writer._conn.execute("PRAGMA journal_mode;")
    journal_mode = cursor.fetchone()[0]
    assert journal_mode.lower() == "wal", f"Expected WAL mode, got {journal_mode}"

    cursor = writer._conn.execute("PRAGMA foreign_keys;")
    foreign_keys = cursor.fetchone()[0]
    assert foreign_keys == 1, "Foreign keys must be enabled"

    writer.close()


def test_foreign_key_constraint_enforcement(tmp_path):
    """Verify that runs cannot reference a nonexistent patient."""
    db_file = str(tmp_path / "fk_test.db")
    writer = PersistenceWriter(db_path=db_file)

    # Attempt to insert run directly without saving patient first
    with pytest.raises(sqlite3.IntegrityError):
        with writer._lock:
            writer._conn.execute(
                """
                INSERT INTO runs (run_id, patient_id, config, status, created_at, updated_at)
                VALUES ('run_orphan', 'nonexistent_pt', '{}', 'queued', 0.0, 0.0);
                """
            )
            writer._conn.commit()

    writer.close()


def test_create_run_and_retrieve_patient(temp_writer, sample_profile, sample_config):
    """Verify patient profile and run creation."""
    temp_writer.create_run(sample_config, sample_profile)

    # Retrieve patient
    retrieved_pt = temp_writer.get_patient_profile(sample_profile.patient_id)
    assert retrieved_pt is not None
    assert retrieved_pt.patient_id == sample_profile.patient_id
    assert retrieved_pt.mass_kg == sample_profile.mass_kg

    # Retrieve run
    run_dict = temp_writer.get_run(sample_config.run_id)
    assert run_dict is not None
    assert run_dict["run_id"] == sample_config.run_id
    assert run_dict["status"] == "queued"


def test_monotonically_sequenced_events_and_catchup(temp_writer, sample_profile, sample_config):
    """Verify event appending and sequence catch-up paging (GET /events?after_seq=N)."""
    temp_writer.create_run(sample_config, sample_profile)

    # Append 10 sequential events
    for seq in range(1, 11):
        event = create_run_created_event(
            run_id=sample_config.run_id,
            sequence=seq,
            config=sample_config,
            profile=sample_profile
        )
        temp_writer.append_event(event)

    # Full retrieval from beginning
    all_events = temp_writer.get_events_after(sample_config.run_id, after_seq=-1, limit=50)
    assert len(all_events) == 10
    assert [e.sequence for e in all_events] == list(range(1, 11))

    # Catch-up query: after sequence 5
    catchup_events = temp_writer.get_events_after(sample_config.run_id, after_seq=5, limit=50)
    assert len(catchup_events) == 5
    assert [e.sequence for e in catchup_events] == [6, 7, 8, 9, 10]


def test_rapid_concurrent_writes(temp_writer, sample_profile, sample_config):
    """Verify thread-safe PersistenceWriter handles rapid concurrent streaming without lock error."""
    temp_writer.create_run(sample_config, sample_profile)

    num_snapshots = 50

    def write_snapshot(seq: int):
        snap = PhysiologySnapshot(
            run_id=sample_config.run_id,
            sequence=seq,
            simulation_time=float(seq),
            quantities={
                "heart_rate": {"value": 72.0 + seq * 0.1, "unit": "bpm", "source": "pulse_engine"}
            },
            coverage_flags={"engine_simulated": "true"},
            is_valid=True
        )
        temp_writer.commit_snapshot(snap)

    # Concurrently write 50 snapshots across 5 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_snapshot, i) for i in range(num_snapshots)]
        for f in concurrent.futures.as_completed(futures):
            f.result()  # Will raise if an exception occurred

    # Check latest snapshot
    latest = temp_writer.get_latest_snapshot(sample_config.run_id)
    assert latest is not None
    assert latest.sequence == num_snapshots - 1


def test_checkpoint_persistence_and_restore(temp_writer, sample_profile, sample_config):
    """Verify checkpoint storage and retrieval."""
    temp_writer.create_run(sample_config, sample_profile)

    checkpoint = Checkpoint(
        checkpoint_id="chk_time_120",
        run_id=sample_config.run_id,
        simulation_time=120.0,
        sequence=120,
        serialized_engine_state='{"vitals": {"hr": 84.0}}',
        event_cursor=5,
        content_hash="hash_chk_120"
    )
    temp_writer.save_checkpoint(checkpoint)

    retrieved_chk = temp_writer.get_checkpoint("chk_time_120")
    assert retrieved_chk is not None
    assert retrieved_chk.simulation_time == 120.0
    assert retrieved_chk.serialized_engine_state == '{"vitals": {"hr": 84.0}}'
    assert retrieved_chk.content_hash == "hash_chk_120"


def test_findings_and_review_persistence(temp_writer, sample_profile, sample_config):
    """Verify organ council findings and clinical review persistence."""
    temp_writer.create_run(sample_config, sample_profile)

    finding = AgentFinding(
        finding_id="find_renal_01",
        run_id=sample_config.run_id,
        sequence=10,
        simulation_time=60.0,
        organ="renal",
        category="hypoperfusion",
        severity="monitor",
        inputs_observed={"map": 64.0, "gfr": 45.0},
        rule_id="RULE_RENAL_001",
        coverage="engine_simulated",
        message="Renal perfusion below nominal threshold."
    )
    temp_writer.save_finding(finding)

    findings = temp_writer.get_findings_for_run(sample_config.run_id)
    assert len(findings) == 1
    assert findings[0].finding_id == "find_renal_01"
    assert findings[0].organ == "renal"

    # Review Record
    review = ReviewRecord(
        review_id="rev_001",
        run_id=sample_config.run_id,
        reviewer="Synthetic Reviewer",
        timestamp=1700000000.0,
        status="approved",
        acknowledged_limitations=["NSAID effect is evidence-only."],
        notes="All checks passed."
    )
    temp_writer.save_review(review)
