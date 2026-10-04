"""
Event types, enums, and factory methods for the Append-Only Event Stream.
Strictly adheres to:
- 2026-10-03-physiological-twin-design.md (Section 6, 8, 12)
- implementation-plan.md (Phase 5)
"""

import time
from enum import Enum
from typing import Dict, Any, List, Optional

from backend.schemas.domain import (
    RunEvent,
    PhysiologySnapshot,
    AgentFinding,
    Checkpoint,
    Intervention,
    SimulationConfig,
    PatientProfile,
)


class EventType(str, Enum):
    RUN_CREATED = "RUN_CREATED"
    RUN_INITIALIZING = "RUN_INITIALIZING"
    RUN_STARTED = "RUN_STARTED"
    INTERVENTION_SCHEDULED = "INTERVENTION_SCHEDULED"
    INTERVENTION_APPLIED = "INTERVENTION_APPLIED"
    SNAPSHOT_COMMITTED = "SNAPSHOT_COMMITTED"
    FINDING_CREATED = "FINDING_CREATED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"


def create_run_created_event(
    run_id: str,
    sequence: int,
    config: SimulationConfig,
    profile: PatientProfile,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=run_id,
        sequence=sequence,
        simulation_time=0.0,
        wall_clock_time=time.time(),
        event_type=EventType.RUN_CREATED.value,
        payload={
            "config": config.model_dump(),
            "profile": profile.model_dump()
        },
        parent_causal_ids=parent_causal_ids or []
    )


def create_intervention_scheduled_event(
    run_id: str,
    sequence: int,
    intervention: Intervention,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=run_id,
        sequence=sequence,
        simulation_time=intervention.simulation_time,
        wall_clock_time=time.time(),
        event_type=EventType.INTERVENTION_SCHEDULED.value,
        payload=intervention.model_dump(),
        parent_causal_ids=parent_causal_ids or []
    )


def create_intervention_applied_event(
    run_id: str,
    sequence: int,
    simulation_time: float,
    intervention: Intervention,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=run_id,
        sequence=sequence,
        simulation_time=simulation_time,
        wall_clock_time=time.time(),
        event_type=EventType.INTERVENTION_APPLIED.value,
        payload=intervention.model_dump(),
        parent_causal_ids=parent_causal_ids or []
    )


def create_snapshot_event(
    snapshot: PhysiologySnapshot,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=snapshot.run_id,
        sequence=snapshot.sequence,
        simulation_time=snapshot.simulation_time,
        wall_clock_time=time.time(),
        event_type=EventType.SNAPSHOT_COMMITTED.value,
        payload=snapshot.model_dump(),
        parent_causal_ids=parent_causal_ids or []
    )


def create_finding_event(
    finding: AgentFinding,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=finding.run_id,
        sequence=finding.sequence,
        simulation_time=finding.simulation_time,
        wall_clock_time=time.time(),
        event_type=EventType.FINDING_CREATED.value,
        payload=finding.model_dump(),
        parent_causal_ids=parent_causal_ids or []
    )


def create_checkpoint_event(
    checkpoint: Checkpoint,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=checkpoint.run_id,
        sequence=checkpoint.sequence,
        simulation_time=checkpoint.simulation_time,
        wall_clock_time=time.time(),
        event_type=EventType.CHECKPOINT_CREATED.value,
        payload={
            "checkpoint_id": checkpoint.checkpoint_id,
            "simulation_time": checkpoint.simulation_time,
            "sequence": checkpoint.sequence,
            "event_cursor": checkpoint.event_cursor,
            "content_hash": checkpoint.content_hash
        },
        parent_causal_ids=parent_causal_ids or []
    )


def create_status_event(
    run_id: str,
    sequence: int,
    simulation_time: float,
    status: EventType,
    details: Optional[Dict[str, Any]] = None,
    parent_causal_ids: Optional[List[str]] = None
) -> RunEvent:
    return RunEvent(
        schema_version="1.0.0",
        run_id=run_id,
        sequence=sequence,
        simulation_time=simulation_time,
        wall_clock_time=time.time(),
        event_type=status.value,
        payload=details or {},
        parent_causal_ids=parent_causal_ids or []
    )
