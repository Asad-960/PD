"""
Pydantic V2 Domain Data Contracts for Physiological Digital Twin Sandbox.
Strictly adheres to:
- 2026-10-03-physiological-twin-design.md (Section 6)
- implementation-plan.md (Phase 3)
"""

import math
from typing import Dict, List, Optional, Union, Literal, Any, Annotated
from pydantic import (
    BaseModel, Field, ConfigDict, model_validator, AfterValidator,
    BeforeValidator, PlainSerializer, StrictBool, StrictInt, StrictStr,
)
from backend.schemas.immutable import freeze, freeze_json, thaw
from simulation.capabilities import INTERVENTION_ALIASES, canonical_identifier

# Engineering bounds for the local demo, not medical safety thresholds.
MAX_HORIZON_SECONDS = 3600
MAX_CADENCE_SNAPSHOTS = 10001
MAX_SCHEDULED_INTERVENTIONS = 500
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Text = Annotated[str, Field(strict=True, min_length=1, max_length=4096)]
FrozenMeasurements = Annotated[Dict[Text, "BaselineMeasurement"], AfterValidator(freeze), PlainSerializer(thaw)]
FrozenContext = Annotated[Dict[Text, Union[StrictBool, StrictStr]], AfterValidator(freeze), PlainSerializer(thaw)]
FrozenStrings = Annotated[Dict[Text, Text], AfterValidator(freeze), PlainSerializer(thaw)]
FrozenQuantities = Annotated[Dict[Text, "QuantitySnapshot"], AfterValidator(freeze), PlainSerializer(thaw)]
FrozenMetadata = Annotated[Dict[Text, Any], BeforeValidator(freeze_json), AfterValidator(freeze_json), PlainSerializer(thaw)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always", validate_assignment=True, validate_default=True)

    def model_copy(self, *, update=None, deep=False):
        # Pydantic's stock copy trusts update data; public contract copies do not.
        raw = self.model_dump()
        raw.update(update or {})
        return type(self).model_validate(raw)

    def copy(self, *, include=None, exclude=None, update=None, deep=False):
        """Compatibility with legacy callers without Pydantic's trusted-update bypass."""
        raw = self.model_dump(include=include, exclude=exclude)
        raw.update(update or {})
        return type(self).model_validate(raw)


class FrozenDomainModel(DomainModel):
    model_config = ConfigDict(frozen=True)


def enforce_payload_budget(model, max_bytes):
    if len(model.model_dump_json().encode("utf-8")) > max_bytes:
        raise ValueError(f"Local payload exceeds {max_bytes} UTF-8 bytes")
    return model


class BaselineMeasurement(FrozenDomainModel):
    """
    Individual baseline measurement with explicit unit, timing, source, and missingness flag.
    Rule 5 Compliance: Missing measurements remain missing. Defaults must NOT be silently inferred.
    """
    name: Text = Field(..., description="Measurement identifier (e.g. egfr, map, creatinine)")
    value: Optional[FiniteNumber] = Field(default=None, description="Measured numerical value, or None if unmeasured")
    unit: Text = Field(..., description="Physical or clinical unit (e.g. mL/min, mmHg, mg/dL)")
    measurement_time: Optional[FiniteNumber] = Field(default=None, description="Simulation or reference time of measurement in seconds")
    source: Text = Field(default="synthetic", description="Provenance of measurement (synthetic, lab, clinical_vitals)")
    is_missing: StrictBool = Field(default=False, description="Flag indicating if the measurement is absent/unmeasured")

    @model_validator(mode="after")
    def enforce_missingness_consistency(self) -> "BaselineMeasurement":
        # Rule 5: If value is None, is_missing MUST be True.
        if self.value is None:
            object.__setattr__(self, "is_missing", True)
        elif self.is_missing and self.value is not None:
            # Cannot have a non-None value if explicitly flagged as missing
            raise ValueError(f"Measurement '{self.name}' has is_missing=True but value={self.value}. Value must be None.")
        return self


class PatientProfile(FrozenDomainModel):
    """
    Synthetic patient specification.
    A clinical diagnosis (e.g. diabetes) does not supply nonexistent measured eGFR or glucose.
    """
    patient_id: Text = Field(..., description="Unique synthetic patient identifier")
    age: StrictInt = Field(..., gt=0, lt=130, description="Age in years")
    sex: Optional[Literal["male", "female"]] = Field(default=None, description="Explicit physiological sex parameter, if supplied; never inferred from gender")
    mass_kg: Optional[FiniteNumber] = Field(default=None, gt=0.0, lt=350.0, description="Patient body mass in kilograms, if measured")
    display_name: Optional[Text] = None
    gender: Text = "not_recorded"
    intake: FrozenMetadata = Field(default_factory=dict, description="Original typed intake and declared unknown states")
    baseline_measurements: FrozenMeasurements = Field(
        default_factory=dict,
        max_length=64,
        description="Explicit baseline physiological and laboratory measurements"
    )
    conditions: tuple[Text, ...] = Field(
        default_factory=tuple,
        max_length=64,
        description="Active chronic conditions (e.g. ChronicRenalStenosis, EssentialHypertension)"
    )
    context: FrozenContext = Field(
        default_factory=dict,
        max_length=64,
        description="Contextual clinical flags (e.g. {'diabetes': True, 'hepatic_impairment': 'moderate'})"
    )
    current_medications: tuple[Text, ...] = Field(
        default_factory=tuple,
        max_length=64,
        description="Current standing medications"
    )
    allergies: tuple[Text, ...] = Field(
        default_factory=tuple,
        max_length=64,
        description="Known substance or medication allergies"
    )

    @model_validator(mode="after")
    def check_baseline_keys(self):
        if any(key != measurement.name for key, measurement in self.baseline_measurements.items()):
            raise ValueError("Baseline measurement key must equal its measurement name")
        return enforce_payload_budget(self, 16 * 1024)


class Intervention(FrozenDomainModel):
    """
    Scheduled or interactive intervention event.
    """
    event_id: Text = Field(..., description="Unique identifier for this intervention")
    ingredient_id: Text = Field(..., description="Normalized active ingredient or intervention identifier")
    dose: FiniteNumber = Field(..., ge=0.0, description="Administered quantity")
    unit: Literal["mg", "g", "mcg", "mL", "L", "fraction", "L/min", "mL/min", "mcg/min"]
    route: Literal["oral", "intravenous", "rectal", "intramuscular", "environmental", "nasal_cannula", "inhaled", "subcutaneous"]
    simulation_time: FiniteNumber = Field(..., ge=0.0, description="Target engine simulation time in seconds")
    duration: FiniteNumber = Field(default=0.0, ge=0.0, description="Duration of administration in seconds (0 for bolus)")
    idempotency_key: Text = Field(..., description="Unique idempotency key to prevent duplicate applications")

    @model_validator(mode="after")
    def check_action_shape(self):
        completion = self.simulation_time + self.duration
        if self.duration > 0 and (not math.isfinite(completion) or completion <= self.simulation_time):
            raise ValueError("Action duration needs a finite representable completion time")
        known = ("IV_Saline_Infusion", "Dehydration", "High_Dose_NSAID", "Morphine")
        action = canonical_identifier(self.ingredient_id, INTERVENTION_ALIASES, known)
        if action in ("IV_Saline_Infusion", "Dehydration"):
            expected_route = "environmental" if action == "Dehydration" else "intravenous"
            units = ("mL", "L", "fraction") if action == "Dehydration" else ("mL", "L")
            if self.route != expected_route or self.unit not in units:
                raise ValueError("Fluid action has incompatible unit or route")
            if self.unit == "fraction" and self.dose > 1:
                raise ValueError("Dehydration fraction must be between 0 and 1")
        if action in ("High_Dose_NSAID", "Morphine") and (
            self.unit not in ("mg", "g") or self.route not in ("oral", "intravenous", "rectal", "intramuscular", "subcutaneous")
        ):
            raise ValueError("Evidence exposure has incompatible unit or route")
        return enforce_payload_budget(self, 2 * 1024)


class SimulationConfig(FrozenDomainModel):
    """
    Simulation configuration specifying engine parameters, horizon, and sampling cadence.
    """
    run_id: Text = Field(..., description="Unique identifier for the simulation run")
    engine_name: Text = Field(default="unverified", description="Requested engine identity; the worker binds an unspecified identity to the actual adapter")
    engine_version: Text = Field(default="unverified", description="Requested engine version; never inferred as Pulse")
    profile_hash: Text = Field(..., description="Profile lineage identifier; canonical hashing enforced with persistence repair")
    horizon_seconds: FiniteNumber = Field(default=300.0, gt=0.0, le=MAX_HORIZON_SECONDS, description="Local run horizon in seconds")
    sample_cadence_seconds: FiniteNumber = Field(default=1.0, gt=0.0, description="Output snapshot sampling cadence in seconds")
    assumptions: FrozenStrings = Field(default_factory=dict, description="Explicit modeling assumptions")

    @model_validator(mode="after")
    def check_sampling_budget(self):
        intervals = self.horizon_seconds / self.sample_cadence_seconds
        if not math.isfinite(intervals) or math.ceil(intervals) + 1 > MAX_CADENCE_SNAPSHOTS:
            raise ValueError("Run exceeds local cadence snapshot budget")
        return enforce_payload_budget(self, 8 * 1024)


class QuantitySnapshot(FrozenDomainModel):
    """
    Individual physiological quantity within a snapshot.
    """
    value: FiniteNumber = Field(..., description="Finite numerical value; absent measurements are omitted, never invented")
    unit: Text = Field(..., description="Measurement unit")
    source: Text = Field(default="unverified", description="Model owner/source of the quantity")
    capability: Literal["engine_simulated", "illustrative", "evidence_only", "unsupported"] = Field(default="unsupported", description="Capability level; provenance must be supplied explicitly")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    @model_validator(mode="after")
    def check_numerical_provenance(self):
        if self.capability == "evidence_only":
            raise ValueError("Evidence-only claims do not supply numerical quantities")
        if self.capability in ("illustrative", "engine_simulated") and self.source == "unverified":
            raise ValueError("Numerical coverage requires an explicit source")
        return self


class PhysiologySnapshot(FrozenDomainModel):
    """
    Immutable snapshot of whole-body physiology at a discrete simulation time point.
    Engine is the sole owner of this state; agents inspect but never mutate.
    """
    run_id: Text = Field(..., description="Run identifier")
    sequence: StrictInt = Field(..., ge=0, description="Monotonically increasing sequence number")
    simulation_time: FiniteNumber = Field(..., ge=0.0, description="Engine simulation time in seconds")
    quantities: FrozenQuantities = Field(
        ...,
        max_length=128,
        description="Keyed physiological metrics with values, units, and sources"
    )
    coverage_flags: FrozenMetadata = Field(
        default_factory=dict,
        description="Coverage flags (e.g. simulated, evidence_only, unsupported)"
    )
    is_valid: StrictBool = Field(default=True, description="Adapter numerical validity; does not establish clinical validity")
    numerical_error_code: Optional[Text] = None
    is_stale: StrictBool = False

    @model_validator(mode="after")
    def check_payload_budget(self):
        return enforce_payload_budget(self, 32 * 1024)


class DraftFinding(FrozenDomainModel):
    """Council output tied to a source snapshot; stream numbering belongs to the writer."""
    run_id: Text
    source_snapshot_sequence: StrictInt = Field(..., ge=0)
    simulation_time: FiniteNumber = Field(..., ge=0)
    organ: Literal["renal", "cardiovascular", "hepatic", "respiratory"]
    category: Text
    severity: Literal["normal", "monitor", "critical", "unknown"]
    inputs_observed: FrozenMetadata = Field(default_factory=dict)
    predicate_outcomes: FrozenMetadata = Field(default_factory=dict)
    missing_inputs: tuple[Text, ...] = Field(default_factory=tuple)
    rule_id: Optional[Text] = None
    evidence_ids: tuple[Text, ...] = Field(default_factory=tuple)
    source_versions: FrozenStrings = Field(default_factory=dict)
    coverage: Literal["engine_simulated", "illustrative", "evidence_only", "unsupported"]
    message: Text
    limitations: Optional[Text] = None
    causal_event_ids: tuple[Text, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def check_payload_budget(self):
        return enforce_payload_budget(self, 16 * 1024)


class AgentFinding(DomainModel):
    """
    Structured finding produced by an organ council agent or evidence evaluator.
    Stored derivation: inputs + rule/model + source + limitations.
    """
    finding_id: Text = Field(..., description="Unique finding identifier")
    run_id: Text = Field(..., description="Associated run identifier")
    sequence: StrictInt = Field(..., ge=0, description="Sequence counter when finding was produced")
    simulation_time: FiniteNumber = Field(..., ge=0.0, description="Simulation time of finding in seconds")
    organ: Literal["renal", "cardiovascular", "hepatic", "respiratory"] = Field(
        ...,
        description="Inspecting organ agent"
    )
    category: Text = Field(..., description="Clinical or physiological category")
    severity: Literal["normal", "monitor", "critical", "unknown"] = Field(
        ...,
        description="Evaluated clinical severity"
    )
    inputs_observed: Dict[Text, Union[FiniteNumber, StrictStr, None]] = Field(
        default_factory=dict,
        description="Actual snapshot values and baseline facts observed by agent"
    )
    rule_id: Optional[Text] = Field(default=None, description="Identifier of the rule that fired")
    evidence_ids: List[Text] = Field(default_factory=list, description="List of evidence citation IDs")
    coverage: Literal["engine_simulated", "illustrative", "evidence_only", "unsupported"] = Field(
        ...,
        description="Capability level of this finding"
    )
    message: Text = Field(..., description="User-facing concise explanation")
    limitations: Optional[Text] = Field(default=None, description="Disclosed modeling limitations and caveats")
    source_snapshot_sequence: Optional[StrictInt] = Field(default=None, ge=0)
    predicate_outcomes: Dict[Text, Any] = Field(default_factory=dict)
    missing_inputs: List[Text] = Field(default_factory=list)
    source_versions: Dict[Text, Text] = Field(default_factory=dict)
    causal_event_ids: List[Text] = Field(default_factory=list)


class RunEvent(DomainModel):
    """
    Event in the run's append-only event stream. Enables full replay and WebSocket sync.
    """
    schema_version: Text = Field(default="1.0.0", description="Event contract schema version")
    run_id: Text = Field(..., description="Run identifier")
    sequence: StrictInt = Field(..., ge=0, description="Monotonically increasing sequence number")
    simulation_time: FiniteNumber = Field(..., ge=0.0, description="Simulation time in seconds")
    wall_clock_time: FiniteNumber = Field(..., description="Unix epoch timestamp when event occurred")
    event_type: Text = Field(..., description="Event type identifier (e.g. RUN_STARTED, INTERVENTION_APPLIED)")
    payload: Annotated[Dict[Text, Any], BeforeValidator(lambda value: thaw(freeze_json(value, max_nodes=4096, max_string_length=256 * 1024)))] = Field(default_factory=dict, description="Event JSON payload; append-only storage enforced separately")
    parent_causal_ids: List[Text] = Field(default_factory=list, description="Lineage / causal tracking IDs")

    @model_validator(mode="after")
    def check_payload_budget(self):
        return enforce_payload_budget(self, 256 * 1024)


class Checkpoint(DomainModel):
    """
    Engine and simulation state checkpoint for branching and time-travel replay.
    """
    checkpoint_id: Text = Field(..., description="Unique checkpoint identifier")
    run_id: Text = Field(..., description="Parent run identifier")
    simulation_time: FiniteNumber = Field(..., ge=0.0, description="Simulation time at checkpoint")
    sequence: StrictInt = Field(..., ge=0, description="Event sequence number at checkpoint")
    serialized_engine_state: StrictStr = Field(..., description="Opaque serialized engine state")
    event_cursor: StrictInt = Field(..., ge=0, description="Last processed event index")
    content_hash: Text = Field(..., description="Cryptographic content hash of checkpoint state")


class ReviewRecord(DomainModel):
    """
    Clinical review or validation audit record.
    Acknowledged limitations explicitly recorded; does not claim clinical validation.
    """
    review_id: Text = Field(..., description="Unique review record identifier")
    run_id: Text = Field(..., description="Associated run identifier")
    reviewer: Text = Field(..., description="Reviewer label or synthetic auditor role")
    timestamp: FiniteNumber = Field(..., description="Unix timestamp of review")
    status: Literal["approved", "rejected", "preliminary"] = Field(..., description="Review status")
    acknowledged_limitations: List[Text] = Field(
        default_factory=list,
        description="Explicitly acknowledged modeling caveats and unsupported mechanisms"
    )
    notes: StrictStr = Field(..., description="Reviewer commentary and observations")
