"""
Single Persistence Writer for SQLite Database.
Strictly adheres to:
- 2026-10-03-physiological-twin-design.md (Section 12: 'Only a single writer commits SQLite changes.')
- implementation-plan.md (Phase 4: 'Implement a single persistence writer.')
"""

import json
import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Any, Optional

from backend.database.schema import init_db, apply_pragmas
from backend.schemas.domain import (
    PatientProfile,
    SimulationConfig,
    RunEvent,
    PhysiologySnapshot,
    AgentFinding,
    Checkpoint,
    ReviewRecord,
    Intervention,
    DraftFinding,
)


def canonical_profile_hash(profile: PatientProfile) -> str:
    """Hash only validated profile content, excluding incidental wall time."""
    data = json.dumps(profile.model_dump(mode="json"), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class PersistenceWriter:
    """
    Thread-safe Single Persistence Writer for SQLite.
    Guarantees:
    - Exclusive serialization of all SQLite mutations via threading locks
    - Zero lock contention in WAL mode
    - Pure domain model parsing without untyped leaks
    - Ordered event stream appended with verified sequence integrity
    """

    _writer_registry_lock = threading.Lock()
    _open_file_paths: set[str] = set()

    def __init__(self, db_path: str = "pdtt.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._registered_path = None if db_path == ":memory:" else str(Path(db_path).resolve())
        with PersistenceWriter._writer_registry_lock:
            if self._registered_path in PersistenceWriter._open_file_paths:
                raise RuntimeError("A persistence writer already owns this database file")
            if self._registered_path is not None:
                PersistenceWriter._open_file_paths.add(self._registered_path)
        try:
            self._conn = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=10.0
            )
            self._conn.row_factory = sqlite3.Row
            with self._lock:
                init_db(self._conn)
            self._closed = False
        except Exception:
            if hasattr(self, "_conn"):
                self._conn.close()
            with PersistenceWriter._writer_registry_lock:
                PersistenceWriter._open_file_paths.discard(self._registered_path)
            raise

    def close(self) -> None:
        """Close database connection cleanly."""
        with self._lock:
            if self._closed:
                return
            try:
                self._conn.close()
            finally:
                self._closed = True
                with PersistenceWriter._writer_registry_lock:
                    PersistenceWriter._open_file_paths.discard(self._registered_path)

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self._conn.in_transaction:
                raise RuntimeError("Persistence transaction already active")
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

    def _require_existing_run(self, run_id: str) -> None:
        if self._conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone() is None:
            raise ValueError(f"Unknown run_id: {run_id}")

    def _insert_exact(self, table: str, identity_column: str, identity: str,
                      columns: tuple, values: tuple, owner: str | None = None) -> bool:
        """Return False for an exact retry; reject changed payloads or ownership."""
        selected = ", ".join(columns)
        row = self._conn.execute(
            f"SELECT {selected} FROM {table} WHERE {identity_column}=?", (identity,)
        ).fetchone()
        if row is not None:
            if owner is not None and "run_id" in columns and row["run_id"] != owner:
                raise ValueError(f"{table} identity belongs to a different run")
            if tuple(row[column] for column in columns) != values:
                raise ValueError(f"Changed retry would rewrite {table} history")
            return False
        marks = ", ".join("?" for _ in columns)
        self._conn.execute(
            f"INSERT INTO {table} ({selected}) VALUES ({marks})", values
        )
        return True

    def _insert_profile(self, profile: PatientProfile) -> None:
        data = canonical_json(profile.model_dump(mode="json"))
        row = self._conn.execute("SELECT data FROM patient_profiles WHERE patient_id=?", (profile.patient_id,)).fetchone()
        if row:
            if canonical_json(json.loads(row["data"])) != data:
                raise ValueError("Patient identity cannot rewrite profile history")
            return
        self._conn.execute(
            "INSERT INTO patient_profiles (patient_id,data,created_at) VALUES (?,?,?)",
            (profile.patient_id, data, time.time()),
        )

    def _insert_snapshot(self, snapshot: PhysiologySnapshot) -> None:
        identity = f"snap_{snapshot.run_id}_{snapshot.sequence}"
        self._require_existing_run(snapshot.run_id)
        self._insert_exact("snapshots", "snapshot_id", identity,
                           ("snapshot_id", "run_id", "sequence", "simulation_time", "data", "is_valid", "is_stale"),
                           (identity, snapshot.run_id, snapshot.sequence, snapshot.simulation_time,
                            canonical_json(snapshot.model_dump(mode="json")), int(snapshot.is_valid), int(snapshot.is_stale)),
                           owner=snapshot.run_id)

    def _insert_event(self, event: RunEvent) -> None:
        event = RunEvent.model_validate(event)
        self._require_existing_run(event.run_id)
        payload = canonical_json(event.payload)
        parents = canonical_json(event.parent_causal_ids)
        existing = self._conn.execute(
            "SELECT simulation_time, schema_version, event_type, payload, parent_causal_ids FROM events WHERE run_id=? AND sequence=?",
            (event.run_id, event.sequence),
        ).fetchone()
        if existing:
            if (existing["simulation_time"], existing["schema_version"], existing["event_type"],
                canonical_json(json.loads(existing["payload"])), canonical_json(json.loads(existing["parent_causal_ids"]))) != (
                    event.simulation_time, event.schema_version, event.event_type, payload, parents):
                raise ValueError("Changed event retry would rewrite history")
            return
        last = self._conn.execute("SELECT MAX(sequence) FROM events WHERE run_id=?", (event.run_id,)).fetchone()[0]
        expected = (last if last is not None else 0) + 1
        if event.sequence != expected:
            raise ValueError(f"Event sequence must be contiguous; expected {expected}")
        self._conn.execute(
            "INSERT INTO events (run_id,sequence,simulation_time,wall_clock_time,schema_version,event_type,payload,parent_causal_ids) VALUES (?,?,?,?,?,?,?,?)",
            (event.run_id, event.sequence, event.simulation_time, event.wall_clock_time,
             event.schema_version, event.event_type, payload, parents),
        )

    def _insert_intervention(self, run_id: str, intervention: Intervention) -> None:
        self._require_existing_run(run_id)
        self._insert_exact("interventions", "event_id", intervention.event_id,
                           ("event_id", "run_id", "simulation_time", "payload"),
                           (intervention.event_id, run_id, intervention.simulation_time,
                            canonical_json(intervention.model_dump(mode="json"))), owner=run_id)

    def _insert_checkpoint(self, checkpoint: Checkpoint) -> None:
        self._require_existing_run(checkpoint.run_id)
        self._insert_exact("checkpoints", "checkpoint_id", checkpoint.checkpoint_id,
                           ("checkpoint_id", "run_id", "sequence", "simulation_time", "serialized_state", "event_cursor", "content_hash"),
                           (checkpoint.checkpoint_id, checkpoint.run_id, checkpoint.sequence,
                            checkpoint.simulation_time, checkpoint.serialized_engine_state,
                            checkpoint.event_cursor, checkpoint.content_hash), owner=checkpoint.run_id)

    def _insert_finding(self, finding: AgentFinding) -> None:
        self._require_existing_run(finding.run_id)
        self._insert_exact("findings", "finding_id", finding.finding_id,
                           ("finding_id", "run_id", "sequence", "simulation_time", "organ", "category", "severity", "coverage", "data"),
                           (finding.finding_id, finding.run_id, finding.sequence,
                            finding.simulation_time, finding.organ, finding.category,
                            finding.severity, finding.coverage,
                            canonical_json(finding.model_dump(mode="json"))), owner=finding.run_id)

    # =========================================================================
    # Write Operations (Atomic & Serialized)
    # =========================================================================

    def save_patient_profile(self, profile: PatientProfile) -> None:
        """Persist a profile once; only exact repeats are accepted."""
        profile = PatientProfile.model_validate(profile)
        with self._transaction():
            self._insert_profile(profile)

    def create_run(self, config: SimulationConfig, profile: PatientProfile,
                   interventions: List[Intervention] = None, created_event: RunEvent = None,
                   assessment_basis: dict = None) -> None:
        """Atomically register immutable profile, config, schedule and optional event."""
        config = SimulationConfig.model_validate(config)
        profile = PatientProfile.model_validate(profile)
        actions = [Intervention.model_validate(item) for item in (interventions or [])]
        if config.profile_hash != canonical_profile_hash(profile):
            raise ValueError("Configuration profile_hash does not match the actual patient profile")
        if any(item.simulation_time + item.duration > config.horizon_seconds for item in actions):
            raise ValueError("Scheduled intervention exceeds the run horizon")
        if created_event is not None:
            expected = {"config": config.model_dump(mode="json"),
                        "profile": profile.model_dump(mode="json")}
            if canonical_json(created_event.payload) != canonical_json(expected):
                raise ValueError("RUN_CREATED payload disagrees with the committed inputs")
        with self._transaction():
            self._insert_profile(profile)
            row = self._conn.execute("SELECT patient_id,config,initial_schedule FROM runs WHERE run_id=?", (config.run_id,)).fetchone()
            config_json = canonical_json(config.model_dump(mode="json"))
            initial_schedule = canonical_json(sorted((item.model_dump(mode="json") for item in actions),
                                                   key=lambda item: item["event_id"]))
            if row:
                if row["patient_id"] != profile.patient_id or canonical_json(json.loads(row["config"])) != config_json:
                    raise ValueError("Run identity cannot rewrite profile or configuration history")
                if canonical_json(json.loads(row["initial_schedule"])) != initial_schedule:
                    raise ValueError("Run identity cannot rewrite its scheduled intervention history")
            else:
                now = time.time()
                self._conn.execute(
                    "INSERT INTO runs (run_id,patient_id,config,initial_schedule,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (config.run_id, profile.patient_id, config_json, initial_schedule, "queued", now, now),
                )
                for item in actions:
                    self._insert_intervention(config.run_id, item)
            if assessment_basis is not None:
                basis_json = canonical_json(assessment_basis)
                if len(basis_json.encode("utf-8")) > 128 * 1024:
                    raise ValueError("Assessment basis exceeds the local storage budget")
                basis_row = self._conn.execute("SELECT data FROM assessment_bases WHERE run_id=?", (config.run_id,)).fetchone()
                if basis_row and basis_row["data"] != basis_json:
                    raise ValueError("Run identity cannot rewrite its assessment basis")
                if not basis_row:
                    self._conn.execute("INSERT INTO assessment_bases (run_id,data) VALUES (?,?)", (config.run_id, basis_json))
            if created_event is not None:
                if created_event.run_id != config.run_id or created_event.event_type != "RUN_CREATED":
                    raise ValueError("Created event does not belong to this run")
                self._insert_event(created_event)

    def update_run_status(self, run_id: str, status: str) -> None:
        """Update run lifecycle status."""
        with self._transaction():
            now = time.time()
            cursor = self._conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status, now, run_id)
            )
            if cursor.rowcount != 1:
                raise ValueError("Cannot update status of unknown run")

    def append_event(self, event: RunEvent) -> None:
        """Append an event to the immutable sequenced event log."""
        with self._transaction():
            self._insert_event(event)

    def commit_transition(self, *, snapshot: PhysiologySnapshot = None,
                          events: List[RunEvent] = None, checkpoint: Checkpoint = None,
                          intervention: Intervention = None, findings: List[AgentFinding] = None,
                          drafts: List[DraftFinding] = None,
                          status: str = None, run_id: str = None) -> List[AgentFinding]:
        """Commit one source transition and all its records, or none of them."""
        events = list(events or [])
        findings = list(findings or [])
        drafts = [DraftFinding.model_validate(item) for item in (drafts or [])]
        identities = [item.run_id for item in (snapshot, checkpoint, *findings, *drafts, *events) if item is not None]
        if run_id is not None:
            identities.append(run_id)
        if not identities or len(set(identities)) != 1:
            raise ValueError("Transition records must share one run_id")
        owner = identities[0]
        if intervention is not None and intervention.simulation_time < 0:
            raise ValueError("Invalid intervention time")
        if drafts and snapshot is None:
            raise ValueError("Draft findings require their source snapshot in this transition")
        if snapshot is not None:
            snapshot_events = [event for event in events if event.event_type == "SNAPSHOT_COMMITTED"]
            if len(snapshot_events) != 1 or canonical_json(snapshot_events[0].payload) != canonical_json(snapshot.model_dump(mode="json")):
                raise ValueError("SNAPSHOT_COMMITTED payload must match the committed snapshot")
        if any(draft.source_snapshot_sequence != snapshot.sequence or
               draft.simulation_time != snapshot.simulation_time for draft in drafts):
            raise ValueError("Draft finding source identity does not match snapshot")
        persisted: List[AgentFinding] = []
        with self._transaction():
            self._require_existing_run(owner)
            if snapshot is not None:
                self._insert_snapshot(PhysiologySnapshot.model_validate(snapshot))
            if checkpoint is not None:
                self._insert_checkpoint(Checkpoint.model_validate(checkpoint))
            if intervention is not None:
                self._insert_intervention(owner, Intervention.model_validate(intervention))
            for finding in findings:
                self._insert_finding(AgentFinding.model_validate(finding))
            for event in events:
                self._insert_event(event)
            unique_drafts = {canonical_json(draft.model_dump(mode="json")): draft for draft in drafts}
            for semantic_json, draft in sorted(unique_drafts.items(), key=lambda item:
                                               (item[1].organ, item[1].category, item[1].rule_id or "", item[0])):
                next_seq = self._conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE run_id=?", (owner,)).fetchone()[0]
                finding = AgentFinding(
                    finding_id="f_" + hashlib.sha256(semantic_json.encode("utf-8")).hexdigest(),
                    run_id=owner, sequence=next_seq, simulation_time=draft.simulation_time,
                    organ=draft.organ, category=draft.category, severity=draft.severity,
                    inputs_observed=dict(draft.model_dump()["inputs_observed"]),
                    predicate_outcomes=draft.model_dump()["predicate_outcomes"],
                    missing_inputs=list(draft.missing_inputs), rule_id=draft.rule_id,
                    evidence_ids=list(draft.evidence_ids), source_versions=draft.model_dump()["source_versions"],
                    coverage=draft.coverage, message=draft.message, limitations=draft.limitations,
                    causal_event_ids=list(draft.causal_event_ids),
                    source_snapshot_sequence=draft.source_snapshot_sequence,
                )
                self._insert_finding(finding)
                self._insert_event(RunEvent(
                    run_id=owner, sequence=next_seq, simulation_time=draft.simulation_time,
                    wall_clock_time=time.time(), event_type="FINDING_CREATED",
                    payload=finding.model_dump(mode="json"),
                    parent_causal_ids=list(draft.causal_event_ids),
                ))
                persisted.append(finding)
            if status is not None:
                cursor = self._conn.execute(
                    "UPDATE runs SET status=?, updated_at=? WHERE run_id=?", (status, time.time(), owner)
                )
                if cursor.rowcount != 1:
                    raise ValueError("Run disappeared during transition")
        return persisted

    def last_event_sequence(self, run_id: str) -> int:
        with self._lock:
            row = self._conn.execute("SELECT MAX(sequence) FROM events WHERE run_id=?", (run_id,)).fetchone()
            return row[0] if row[0] is not None else 0

    def commit_snapshot(self, snapshot: PhysiologySnapshot) -> None:
        """Legacy single-record adapter; worker uses a transition bundle."""
        with self._transaction():
            self._insert_snapshot(PhysiologySnapshot.model_validate(snapshot))

    def save_finding(self, finding: AgentFinding) -> None:
        """Legacy single-record adapter; council will use draft bundles."""
        with self._transaction():
            self._insert_finding(AgentFinding.model_validate(finding))

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Legacy single-record adapter; worker uses a transition bundle."""
        with self._transaction():
            self._insert_checkpoint(Checkpoint.model_validate(checkpoint))

    def save_intervention(self, run_id: str, intervention: Intervention) -> None:
        """Record an intervention with immutable global identity."""
        with self._transaction():
            self._insert_intervention(run_id, Intervention.model_validate(intervention))

    def save_review(self, review: ReviewRecord) -> None:
        """Persist a review audit record."""
        review = ReviewRecord.model_validate(review)
        with self._transaction():
            self._require_existing_run(review.run_id)
            self._insert_exact("reviews", "review_id", review.review_id,
                               ("review_id", "run_id", "reviewer", "timestamp", "status", "acknowledged_limitations", "notes"),
                               (review.review_id, review.run_id, review.reviewer, review.timestamp,
                                review.status, canonical_json(review.acknowledged_limitations), review.notes),
                               owner=review.run_id)

    # =========================================================================
    # Read Operations
    # =========================================================================

    def get_patient_profile(self, patient_id: str) -> Optional[PatientProfile]:
        """Fetch patient profile by ID."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT data FROM patient_profiles WHERE patient_id = ?",
                (patient_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PatientProfile.model_validate_json(row["data"])

    def read_assessment(self, run_id: str, cursor: Optional[int] = None):
        """Freeze the report's read horizon while the worker can keep appending."""
        with self._lock:
            run = self.get_run(run_id)
            if run is None:
                raise ValueError("Run not found")
            latest = self.last_event_sequence(run_id)
            cursor = latest if cursor is None else cursor
            if type(cursor) is not int or not 0 <= cursor <= latest:
                raise ValueError("Report cursor is outside the recorded run")
            cached = self._conn.execute("SELECT data FROM assessment_reports WHERE run_id=? AND event_cursor=?", (run_id, cursor)).fetchone()
            if cached:
                return {"cached": json.loads(cached["data"])}
            profile = self.get_patient_profile(run["patient_id"])
            rows = self._conn.execute("SELECT sequence,event_type,payload,simulation_time FROM events WHERE run_id=? AND sequence<=? ORDER BY sequence", (run_id, cursor)).fetchall()
            basis = self._conn.execute("SELECT data FROM assessment_bases WHERE run_id=?", (run_id,)).fetchone()
            return {"run": run, "profile": profile.model_dump(mode="json"), "cursor": cursor,
                    "assessment_basis": json.loads(basis["data"]) if basis else None,
                    "events": [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]}

    def cache_assessment(self, report):
        with self._transaction():
            existing = self._conn.execute("SELECT data FROM assessment_reports WHERE run_id=? AND event_cursor=?", (report["run_id"], report["cursor"])).fetchone()
            if existing:
                return json.loads(existing["data"])
            self._conn.execute("INSERT INTO assessment_reports (run_id,event_cursor,report_id,data) VALUES (?,?,?,?)", (report["run_id"], report["cursor"], report["report_id"], canonical_json(report)))
            return json.loads(canonical_json(report))

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch run metadata and configuration."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT run_id, patient_id, config, initial_schedule, status, created_at, updated_at FROM runs WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "run_id": row["run_id"],
                "patient_id": row["patient_id"],
                "config": json.loads(row["config"]),
                "initial_schedule": json.loads(row["initial_schedule"]),
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }

    def get_events_after(self, run_id: str, after_seq: int = -1, limit: int = 100) -> List[RunEvent]:
        """Fetch a page of sequenced events strictly after sequence number `after_seq`."""
        if (type(after_seq) is not int or after_seq < -1 or
                type(limit) is not int or not 1 <= limit <= 500):
            raise ValueError("Event cursor must be >= -1 and page limit must be 1..500")
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT run_id, sequence, simulation_time, wall_clock_time,
                       schema_version, event_type, payload, parent_causal_ids
                FROM events
                WHERE run_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (run_id, after_seq, limit)
            )
            events: List[RunEvent] = []
            for row in cursor.fetchall():
                events.append(
                    RunEvent(
                        schema_version=row["schema_version"],
                        run_id=row["run_id"],
                        sequence=row["sequence"],
                        simulation_time=row["simulation_time"],
                        wall_clock_time=row["wall_clock_time"],
                        event_type=row["event_type"],
                        payload=json.loads(row["payload"]),
                        parent_causal_ids=json.loads(row["parent_causal_ids"])
                    )
                )
            return events

    def get_latest_snapshot(self, run_id: str) -> Optional[PhysiologySnapshot]:
        """Fetch the most recent committed physiological snapshot for a run."""
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT data FROM snapshots
                WHERE run_id = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (run_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PhysiologySnapshot.model_validate_json(row["data"])

    def get_interventions_for_run(self, run_id: str) -> List[Intervention]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM interventions WHERE run_id=? ORDER BY simulation_time,event_id", (run_id,)
            ).fetchall()
            return [Intervention.model_validate_json(row["payload"]) for row in rows]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Fetch a checkpoint by ID."""
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT checkpoint_id, run_id, sequence, simulation_time,
                       serialized_state, event_cursor, content_hash
                FROM checkpoints
                WHERE checkpoint_id = ?
                """,
                (checkpoint_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return Checkpoint(
                checkpoint_id=row["checkpoint_id"],
                run_id=row["run_id"],
                sequence=row["sequence"],
                simulation_time=row["simulation_time"],
                serialized_engine_state=row["serialized_state"],
                event_cursor=row["event_cursor"],
                content_hash=row["content_hash"]
            )

    def get_findings_for_run(self, run_id: str) -> List[AgentFinding]:
        """Fetch all findings recorded for a simulation run in sequence order."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT data FROM findings WHERE run_id = ? ORDER BY sequence ASC",
                (run_id,)
            )
            findings: List[AgentFinding] = []
            for row in cursor.fetchall():
                findings.append(AgentFinding.model_validate_json(row["data"]))
            return findings
