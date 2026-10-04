import time
import threading
import hashlib
import json
from collections import deque
from typing import Optional, List, TYPE_CHECKING
if TYPE_CHECKING:
    from backend.council import OrganCouncil

from backend.schemas.domain import PatientProfile, SimulationConfig, Intervention, Checkpoint, PhysiologySnapshot, MAX_SCHEDULED_INTERVENTIONS
from backend.database.writer import PersistenceWriter, canonical_profile_hash
from backend.events.types import (
    create_run_created_event,
    create_status_event,
    create_intervention_applied_event,
    create_snapshot_event,
    create_checkpoint_event,
    EventType
)
from simulation.coverage import CoverageGate
from simulation.adapter import PhysiologyEngineAdapter, IllustrativeEngineAdapter
from simulation.capabilities import INTERVENTION_ALIASES, canonical_identifier


class SimulationWorker:
    """
    Simulation Worker driving the engine lifecycle and event timing.
    Strictly adheres to:
    - 2026-10-03-physiological-twin-design.md (Section 8: Engine Sandbox & Threading)
    - implementation-plan.md (Phase 6: Simulation Worker)
    """

    _active_runs: set[str] = set()
    _active_runs_lock = threading.Lock()

    def __init__(
        self,
        run_id: str,
        profile: PatientProfile,
        config: SimulationConfig,
        interventions: List[Intervention],
        writer: PersistenceWriter,
        coverage_gate: Optional[CoverageGate] = None,
        engine_adapter: Optional[PhysiologyEngineAdapter] = None,
        council: Optional["OrganCouncil"] = None,
    ):
        profile = PatientProfile.model_validate(profile)
        config = SimulationConfig.model_validate(config)
        if run_id != config.run_id:
            raise ValueError("Worker run_id and configuration run_id disagree")
        self.run_id = run_id
        self.profile = profile.model_copy(deep=True)
        self.engine = engine_adapter or IllustrativeEngineAdapter()
        capabilities = self.engine.capabilities()
        if config.engine_name not in ("unverified", capabilities["engine_name"]) or config.engine_version not in ("unverified", capabilities["engine_version"]):
            raise ValueError("Requested engine does not match the active adapter; no silent fallback is allowed")
        self.config = config.model_copy(deep=True, update={
            "engine_name": capabilities["engine_name"], "engine_version": capabilities["engine_version"],
            "profile_hash": canonical_profile_hash(self.profile),
            "assumptions": {**config.assumptions, "execution_mode": capabilities["execution_mode"],
                            "provenance": capabilities["provenance_statement"]},
        })
        if len(interventions) > MAX_SCHEDULED_INTERVENTIONS:
            raise ValueError("Schedule exceeds local intervention budget")
        unique_actions = []
        seen_keys = {}
        seen_ids = {}
        for item in interventions:
            action = Intervention.model_validate(item)
            canonical = canonical_identifier(action.ingredient_id, INTERVENTION_ALIASES,
                                             capabilities["interventions"]) or action.ingredient_id
            semantic = (canonical, action.dose, action.unit, action.route,
                        action.simulation_time, action.duration)
            if action.event_id in seen_ids and seen_ids[action.event_id] != (action.idempotency_key, semantic):
                raise ValueError("Duplicate event_id has conflicting action content")
            seen_ids[action.event_id] = (action.idempotency_key, semantic)
            prior = seen_keys.get(action.idempotency_key)
            if prior is not None:
                if prior != semantic:
                    raise ValueError("Conflicting intervention idempotency key")
                continue
            seen_keys[action.idempotency_key] = semantic
            unique_actions.append(action)
        self.interventions = tuple(sorted(unique_actions, key=lambda i: i.simulation_time))
        if any(i.simulation_time > self.config.horizon_seconds or
               i.simulation_time + i.duration > self.config.horizon_seconds for i in self.interventions):
            raise ValueError("Intervention start/completion exceeds the run horizon")
        self.writer = writer
        self.council = council
        self.coverage_gate = coverage_gate or CoverageGate(manifest=capabilities)
        if self.coverage_gate._manifest != capabilities:
            raise ValueError("Coverage manifest disagrees with active engine capabilities")
        
        # Single unified monotonic sequence counter to guarantee primary key uniqueness
        self._current_seq: int = 0
        
        # Threading controls
        self._cancelled = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._control = threading.Condition()
        self._commands = deque()
        self._control_state = "new"
        self._claimed = False

    def pause(self) -> None:
        """Queue a pause request; worker acknowledges at its next safe boundary."""
        with self._control:
            if self._control_state in ("cancelled", "failed", "completed"):
                raise RuntimeError("Run is terminal")
            self._commands.append("pause")
            self._control.notify_all()

    def resume(self) -> None:
        """Queue resume; a preceding pause remains ordered and auditable."""
        with self._control:
            if self._control_state in ("cancelled", "failed", "completed"):
                raise RuntimeError("Run is terminal")
            self._commands.append("resume")
            self._control.notify_all()

    def cancel(self) -> None:
        """Queue cancellation and wake a paused worker."""
        with self._control:
            if self._control_state in ("cancelled", "failed", "completed"):
                return
            self._cancelled.set()
            self._commands.append("cancel")
            self._control.notify_all()

    def start_in_background(self) -> threading.Thread:
        """Launch the worker in a background daemon thread."""
        with self._lock:
            if self._thread is not None:
                if self._thread.is_alive():
                    return self._thread
                raise RuntimeError("Worker has already finished")
            if self._claimed:
                raise RuntimeError("Worker already running synchronously")
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
            return self._thread

    def _drain_controls(self, simulation_time: float) -> bool:
        """Apply queued commands on the owner thread after engine boundaries."""
        while True:
            with self._control:
                if self._commands:
                    command = self._commands.popleft()
                elif self._control_state == "paused":
                    self._control.wait()
                    continue
                else:
                    return self._control_state != "cancelled"
            if command == "pause" and self._control_state == "running":
                self.writer.commit_transition(run_id=self.run_id, status="paused", events=[
                    create_status_event(self.run_id, self._next_seq(), simulation_time, EventType.RUN_PAUSED)
                ])
                self._control_state = "paused"
            elif command == "resume" and self._control_state == "paused":
                self.writer.commit_transition(run_id=self.run_id, status="running", events=[
                    create_status_event(self.run_id, self._next_seq(), simulation_time, EventType.RUN_RESUMED)
                ])
                self._control_state = "running"
            elif command == "cancel":
                self.writer.commit_transition(run_id=self.run_id, status="cancelled", events=[
                    create_status_event(self.run_id, self._next_seq(), simulation_time, EventType.RUN_CANCELLED)
                ])
                self._control_state = "cancelled"
                return False

    def _next_seq(self) -> int:
        with self._lock:
            self._current_seq += 1
            return self._current_seq

    def _emit_event(self, event) -> None:
        self.writer.append_event(event)

    def _capture_snapshot(self) -> PhysiologySnapshot:
        raw = self.engine.snapshot()
        raw["run_id"] = self.run_id
        raw["sequence"] = 0
        snapshot = PhysiologySnapshot.model_validate(raw)
        if not snapshot.is_valid:
            raise RuntimeError(f"Engine returned invalid numerical state: {snapshot.numerical_error_code}")
        return snapshot.model_copy(update={"sequence": self._next_seq()})

    def _commit_snapshot(self, snapshot: PhysiologySnapshot,
                         applied: List[Intervention]) -> None:
        drafts = list(self.council.evaluate(self.profile, snapshot, applied)) if self.council else []
        self.writer.commit_transition(snapshot=snapshot, events=[create_snapshot_event(snapshot)],
                                      drafts=drafts)
        # The writer assigns distinct stream sequences to every council finding.
        self._current_seq = self.writer.last_event_sequence(self.run_id)

    def _checkpoint(self, checkpoint_id: str, simulation_time: float,
                    pending: List[Intervention]) -> Checkpoint:
        """Capture engine and deterministic worker schedule at the same boundary."""
        seq = self._next_seq()
        pending_keys = {action.idempotency_key for action in pending}
        state = {
            "schema_version": "worker-checkpoint-1",
            "engine_state": self.engine.serialize(),
            "pending_schedule": [action.model_dump() for action in pending],
            "applied_keys": [action.idempotency_key for action in self.interventions
                             if action.idempotency_key not in pending_keys],
            "profile_hash": self.config.profile_hash,
            "engine_name": self.config.engine_name,
            "engine_version": self.config.engine_version,
            "simulation_time": simulation_time,
            "event_cursor": seq,
        }
        serialized = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return Checkpoint(
            checkpoint_id=checkpoint_id, run_id=self.run_id,
            simulation_time=simulation_time, sequence=seq,
            serialized_engine_state=serialized, event_cursor=seq,
            content_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        )

    def run(self) -> None:
        """Run the simulation lifecycle to completion synchronously."""
        with self._lock:
            if self._claimed:
                raise RuntimeError("Worker already started")
            self._claimed = True
        with SimulationWorker._active_runs_lock:
            if self.run_id in SimulationWorker._active_runs:
                raise RuntimeError("Another worker already owns this run")
            stored = self.writer.get_run(self.run_id)
            if stored is not None and stored["status"] != "queued":
                raise RuntimeError("Existing run cannot be restarted by a new worker")
            SimulationWorker._active_runs.add(self.run_id)
        try:
            self._run_impl()
        except Exception as e:
            # Failed bundle sequence allocations were never committed.
            self._current_seq = self.writer.last_event_sequence(self.run_id)
            try:
                self.writer.commit_transition(
                    run_id=self.run_id, status="failed",
                    events=[create_status_event(
                        run_id=self.run_id,
                        sequence=self._next_seq(),
                        simulation_time=getattr(self.engine, "simulation_time", 0.0),
                        status=EventType.RUN_FAILED,
                        details={"error": str(e)}
                    )]
                )
            except Exception:
                # Preserve the first failure if the writer itself is unavailable.
                pass
            self._control_state = "failed"
            raise
        finally:
            with SimulationWorker._active_runs_lock:
                SimulationWorker._active_runs.discard(self.run_id)

    def _run_impl(self) -> None:
        # Step 1: Validate & Pre-flight
        profile_dump = self.profile.model_dump()
        interventions_dump = [i.model_dump() for i in self.interventions]
        coverage_report = self.coverage_gate.validate_scenario(profile_dump, interventions_dump)

        # Register immutable inputs and the first event in one transaction.
        self.writer.create_run(
            self.config, self.profile, list(self.interventions),
            created_event=create_run_created_event(
                run_id=self.run_id,
                sequence=self._next_seq(),
                config=self.config,
                profile=self.profile
            )
        )

        if not coverage_report.is_runnable:
            raise ValueError("Scenario contains unsupported executable interventions")

        # Persist RUN_INITIALIZING
        self.writer.commit_transition(
            run_id=self.run_id, status="initializing",
            events=[create_status_event(
                run_id=self.run_id,
                sequence=self._next_seq(),
                simulation_time=0.0,
                status=EventType.RUN_INITIALIZING,
                details={"coverage_report": coverage_report.model_dump()}
            )]
        )

        # Step 2: Engine Initialization
        if not self.engine.initialize(profile_dump, self.config.model_dump()["assumptions"]):
            raise RuntimeError("Engine rejected initialization")
        
        # Persist initial baseline snapshot (t = 0.0s)
        snap = self._capture_snapshot()
        self._commit_snapshot(snap, [])

        # Create initial checkpoint
        chk = self._checkpoint(f"chk_init_{self.run_id}", 0.0, list(self.interventions))
        self.writer.commit_transition(checkpoint=chk, events=[create_checkpoint_event(chk)])

        # Mark RUN_STARTED
        self.writer.commit_transition(
            run_id=self.run_id, status="running",
            events=[create_status_event(
                run_id=self.run_id,
                sequence=self._next_seq(),
                simulation_time=0.0,
                status=EventType.RUN_STARTED
            )]
        )
        self._control_state = "running"
        if not self._drain_controls(0.0):
            return

        # Step 3: Discrete Advance Loop
        t_current = 0.0
        cadence = self.config.sample_cadence_seconds
        horizon = self.config.horizon_seconds
        
        interventions_queue = list(self.interventions)
        applied_actions: List[Intervention] = []

        while t_current < horizon:
            if not self._drain_controls(t_current):
                return

            t_next = min(t_current + cadence, horizon)

            # Step 4: Interval Splitting (Mandatory Rule)
            # Find interventions scheduled strictly after t_current and up to t_next
            while interventions_queue and interventions_queue[0].simulation_time <= t_next:
                inv = interventions_queue.pop(0)
                t_int = inv.simulation_time
                
                # Make sure we don't go backwards if an event is scheduled before t_current somehow (shouldn't happen with valid inputs)
                if t_int > t_current:
                    # a. Advance engine from t_current to t_int
                    if not self.engine.advance(t_int - t_current):
                        raise RuntimeError("Engine rejected advance")
                    t_current = t_int
                    if not self._drain_controls(t_current):
                        return
                elif not self._drain_controls(t_current):
                    return

                # b. Automatically save a Checkpoint pre_intervention
                chk = self._checkpoint(f"pre_intervention_{inv.event_id}",
                                       t_current, [inv, *interventions_queue])
                self.writer.commit_transition(checkpoint=chk, events=[create_checkpoint_event(chk)])

                # c. Apply the intervention
                inv_dict = inv.model_dump()
                if "name" not in inv_dict:
                    inv_dict["name"] = inv.ingredient_id
                if not self.engine.apply_event(inv_dict):
                    raise RuntimeError("Engine rejected action")

                # d. Emit INTERVENTION_APPLIED
                applied_event = create_intervention_applied_event(
                        run_id=self.run_id,
                        sequence=self._next_seq(),
                        simulation_time=t_current,
                        intervention=inv
                    )
                action_coverage = self.coverage_gate.evaluate_intervention(inv.ingredient_id)
                applied_event.payload.update(
                    execution_mode=self.engine.capabilities()["execution_mode"],
                    coverage=action_coverage["capability"].value,
                    numerical_applied=bool(action_coverage["numerical_effect"] and inv.dose > 0),
                )
                self.writer.commit_transition(run_id=self.run_id, intervention=inv,
                                              events=[applied_event])
                applied_actions.append(inv)
                if not self._drain_controls(t_current):
                    return
                
            # e. Advance remainder to t_next
            if t_next > t_current:
                if not self.engine.advance(t_next - t_current):
                    raise RuntimeError("Engine rejected advance")
                t_current = t_next
                if not self._drain_controls(t_current):
                    return

            # Step 5: Snapshot & Commit
            snap = self._capture_snapshot()
            self._commit_snapshot(snap, applied_actions)
            if not self._drain_controls(t_current):
                return

        # Step 6: Completion
        self.writer.commit_transition(
            run_id=self.run_id, status="completed",
            events=[create_status_event(
                run_id=self.run_id,
                sequence=self._next_seq(),
                simulation_time=t_current,
                status=EventType.RUN_COMPLETED
            )]
        )
        self._control_state = "completed"
