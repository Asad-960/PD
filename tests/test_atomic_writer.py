"""Durable transition, identity and migration acceptance cases for R3."""
import hashlib
import json
import sqlite3

import pytest

from backend.database.writer import PersistenceWriter
from backend.schemas.domain import PatientProfile, SimulationConfig, Intervention, PhysiologySnapshot, DraftFinding
from backend.events.types import create_status_event, create_snapshot_event, EventType


def patient(name="p", age=45):
    return PatientProfile(patient_id=name, age=age, sex="male", mass_kg=70)


def digest(profile):
    raw = json.dumps(profile.model_dump(mode="json"), sort_keys=True,
                     separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def config(run="r", profile=None, **changes):
    p = profile or patient()
    raw = dict(run_id=run, profile_hash=digest(p), horizon_seconds=10)
    raw.update(changes)
    return SimulationConfig(**raw)


def saline(event_id="fluid", when=0):
    return Intervention(event_id=event_id, ingredient_id="saline", dose=500,
                        unit="mL", route="intravenous", simulation_time=when,
                        idempotency_key=event_id)


def snapshot(seq=1, run="r"):
    return PhysiologySnapshot(run_id=run, sequence=seq, simulation_time=0,
                              quantities={"heart_rate": {"value": 72, "unit": "bpm",
                                                         "source": "test"}})


@pytest.fixture
def writer(tmp_path):
    w = PersistenceWriter(str(tmp_path / "atomic.db"))
    try:
        yield w
    finally:
        w.close()


def test_profile_hash_matches_actual_profile_and_identical_create_is_a_retry(writer):
    p, c = patient(), config()
    writer.create_run(c, p, [saline()])
    writer.create_run(c, p, [saline()])
    assert writer.get_run("r")["config"]["profile_hash"] == digest(p)
    assert len(writer.get_interventions_for_run("r")) == 1


def test_changed_run_or_profile_or_schedule_cannot_rewrite_history(writer):
    p, c = patient(), config()
    writer.create_run(c, p, [saline()])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.create_run(c.model_copy(update={"horizon_seconds": 9}), p, [saline()])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.create_run(c, patient(age=46), [saline()])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.create_run(c, p, [saline(when=2)])
    assert writer.get_run("r")["config"]["horizon_seconds"] == 10
    assert writer.get_patient_profile("p") == p


def test_wrong_profile_digest_rejected_before_any_run_write(writer):
    with pytest.raises(ValueError, match="hash"):
        writer.create_run(config(profile_hash="incorrect"), patient())
    assert writer.get_run("r") is None


def test_snapshot_and_event_roll_back_together_on_late_event_failure(tmp_path):
    class FailingWriter(PersistenceWriter):
        def _insert_event(self, event):
            raise RuntimeError("injected event insert failure")

    w = FailingWriter(str(tmp_path / "fault.db"))
    try:
        w.create_run(config(), patient())
        s = snapshot()
        with pytest.raises(RuntimeError, match="injected event insert"):
            w.commit_transition(snapshot=s, events=[create_snapshot_event(s)])
        assert w.get_latest_snapshot("r") is None
        assert w.get_events_after("r") == []
        assert not w._conn.in_transaction
    finally:
        w.close()


def test_event_version_and_increasing_order_round_trip(writer):
    writer.create_run(config(), patient())
    event = create_status_event("r", 1, 0, EventType.RUN_STARTED)
    event.schema_version = "2.0.0"
    writer.append_event(event)
    assert writer.get_events_after("r")[0].schema_version == "2.0.0"
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.append_event(create_status_event("r", 0, 0, EventType.RUN_PAUSED))
    assert len(writer.get_events_after("r")) == 1


def test_snapshot_retry_is_exact_or_rejected(writer):
    writer.create_run(config(), patient())
    s = snapshot()
    writer.commit_snapshot(s)
    writer.commit_snapshot(s)
    changed = s.model_copy(update={"quantities": {
        "heart_rate": {"value": 71, "unit": "bpm", "source": "test"}}})
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.commit_snapshot(changed)
    assert writer.get_latest_snapshot("r") == s


def test_global_action_identity_cannot_cross_runs(writer):
    writer.create_run(config(), patient())
    writer.create_run(config("branch"), patient())
    writer.save_intervention("r", saline())
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.save_intervention("branch", saline())


def test_new_event_cannot_skip_a_sequence(writer):
    writer.create_run(config(), patient())
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.append_event(create_status_event("r", 2, 0, EventType.RUN_STARTED))
    writer.append_event(create_status_event("r", 1, 0, EventType.RUN_STARTED))
    assert [e.sequence for e in writer.get_events_after("r")] == [1]


def test_original_run_retry_survives_later_admitted_action(writer):
    c, p = config(), patient()
    writer.create_run(c, p, [saline()])
    writer.save_intervention("r", saline(event_id="later", when=2))
    writer.create_run(c, p, [saline()])
    assert len(writer.get_interventions_for_run("r")) == 2


def test_unversioned_database_is_preserved_and_rejected(tmp_path):
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE patient_profiles (patient_id TEXT PRIMARY KEY, data TEXT)")
    conn.execute("INSERT INTO patient_profiles VALUES ('legacy', '{}')")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="Legacy|unversioned"):
        PersistenceWriter(str(old))
    conn = sqlite3.connect(old)
    try:
        assert conn.execute("SELECT patient_id FROM patient_profiles").fetchone()[0] == "legacy"
    finally:
        conn.close()


def test_two_drafts_get_distinct_event_sequences_and_preserve_source_snapshot(writer):
    writer.create_run(config(), patient())
    s = snapshot(seq=1)
    drafts = [DraftFinding(run_id="r", source_snapshot_sequence=1,
                           simulation_time=0, organ=organ, category="coverage",
                           severity="unknown", coverage="unsupported",
                           message=f"{organ} mechanism not modeled",
                           predicate_outcomes={"modeled": False},
                           missing_inputs=["validated_engine"])
              for organ in ("renal", "hepatic")]
    persisted = writer.commit_transition(snapshot=s, events=[create_snapshot_event(s)], drafts=drafts)
    assert [e.sequence for e in writer.get_events_after("r")] == [1, 2, 3]
    assert {f.organ for f in persisted} == {"renal", "hepatic"}
    assert {f.source_snapshot_sequence for f in persisted} == {1}
    assert {f.sequence for f in persisted} == {2, 3}
    assert all(f.coverage == "unsupported" for f in writer.get_findings_for_run("r"))


def test_draft_failure_rolls_back_snapshot_and_all_findings(tmp_path):
    class FailingWriter(PersistenceWriter):
        def _insert_finding(self, finding):
            if finding.organ == "renal":
                raise RuntimeError("injected second finding failure")
            return super()._insert_finding(finding)

    w = FailingWriter(str(tmp_path / "draft-fault.db"))
    try:
        w.create_run(config(), patient())
        s = snapshot()
        drafts = [DraftFinding(run_id="r", source_snapshot_sequence=1,
                               simulation_time=0, organ=organ, category="coverage",
                               severity="unknown", coverage="unsupported", message=organ)
                  for organ in ("hepatic", "renal")]
        with pytest.raises(RuntimeError, match="second finding"):
            w.commit_transition(snapshot=s, events=[create_snapshot_event(s)], drafts=drafts)
        assert w.get_latest_snapshot("r") is None
        assert w.get_findings_for_run("r") == []
        assert w.get_events_after("r") == []
        assert not w._conn.in_transaction
    finally:
        w.close()


def test_only_one_application_writer_can_hold_a_file(tmp_path):
    path = str(tmp_path / "shared.db")
    owner = PersistenceWriter(path)
    try:
        with pytest.raises(RuntimeError, match="writer"):
            PersistenceWriter(path)
    finally:
        owner.close()
    reopened = PersistenceWriter(path)
    try:
        owner.close()  # A repeated close must not release the new owner's lease.
        with pytest.raises(RuntimeError, match="writer"):
            PersistenceWriter(path)
    finally:
        reopened.close()


def test_run_created_event_must_describe_committed_inputs(writer):
    event = create_status_event("r", 1, 0, EventType.RUN_CREATED)
    with pytest.raises(ValueError, match="payload"):
        writer.create_run(config(), patient(), created_event=event)
    assert writer.get_run("r") is None


def test_snapshot_event_payload_must_match_committed_snapshot(writer):
    writer.create_run(config(), patient())
    s = snapshot()
    wrong = create_snapshot_event(s.model_copy(update={"quantities": {
        "heart_rate": {"value": 1, "unit": "bpm", "source": "test"}}}))
    with pytest.raises(ValueError, match="payload"):
        writer.commit_transition(snapshot=s, events=[wrong])
    assert writer.get_latest_snapshot("r") is None


@pytest.mark.parametrize("cursor,limit", [(-2, 10), (0, 0), (0, 501),
                                          (True, 10), (0, True)])
def test_event_pages_are_bounded_and_cursors_are_typed(writer, cursor, limit):
    writer.create_run(config(), patient())
    with pytest.raises(ValueError):
        writer.get_events_after("r", after_seq=cursor, limit=limit)


def test_intervention_schedule_is_visible_with_run_metadata(writer):
    writer.create_run(config(), patient(), [saline(when=2)])
    data = writer.get_run("r")
    assert data["initial_schedule"][0]["simulation_time"] == 2
