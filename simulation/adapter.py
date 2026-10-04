"""Engine boundary and explicitly illustrative development adapter.

No Pulse execution, reference trace or personalized physiological prediction is
implemented here. Drug/disease response belongs in a verified external engine.
"""
import abc
import copy
import hashlib
import json
import math
from typing import Any, Dict, Optional

from simulation.capabilities import (
    CapabilityManifest, INTERVENTION_ALIASES, canonical_identifier, load_manifest,
)


class PhysiologyEngineAdapter(abc.ABC):
    @abc.abstractmethod
    def capabilities(self) -> Dict[str, Any]: ...
    @abc.abstractmethod
    def initialize(self, profile: Dict[str, Any], assumptions: Optional[Dict[str, Any]] = None) -> bool: ...
    @abc.abstractmethod
    def apply_event(self, event: Dict[str, Any]) -> bool: ...
    @abc.abstractmethod
    def advance(self, delta_seconds: float) -> bool: ...
    @abc.abstractmethod
    def snapshot(self) -> Dict[str, Any]: ...
    @abc.abstractmethod
    def serialize(self) -> str: ...
    @abc.abstractmethod
    def restore(self, checkpoint: str) -> bool: ...


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return float(value)


class IllustrativeEngineAdapter(PhysiologyEngineAdapter):
    """Fixed educational values plus total-fluid amount bookkeeping.

    A fluid amount does not predict intravascular volume, drug concentrations,
    blood pressure, organ function or patient outcomes. Clinical measurements
    remain separate profile inputs; none is silently used as a model baseline.
    """
    ENGINE_NAME = "PDTT Illustrative Fluid Bookkeeping"
    ENGINE_VERSION = "0.2.0"
    BASELINE = {
        "heart_rate": 72.0, "mean_arterial_pressure": 93.3,
        "systolic_arterial_pressure": 120.0, "diastolic_arterial_pressure": 80.0,
        "cardiac_output": 5.2, "central_venous_pressure": 4.5,
        "systemic_vascular_resistance": 17.5, "renal_blood_flow": 1200.0,
        "glomerular_filtration_rate": 115.0, "urine_production_rate": 1.2,
        "blood_urea_nitrogen": 14.0, "serum_creatinine": 0.95,
        "respiration_rate": 14.0, "oxygen_saturation": 98.2,
        "end_tidal_carbon_dioxide": 38.0, "arterial_partial_pressure_oxygen": 95.0,
        "arterial_partial_pressure_carbon_dioxide": 40.0, "arterial_blood_ph": 7.4,
        "hepatic_blood_flow": 1450.0, "total_fluid_volume": 42.0,
    }

    def __init__(self, manifest: Optional[Dict[str, Any]] = None):
        builtin = load_manifest().model_dump(mode="json")
        supplied = builtin if manifest is None else CapabilityManifest.model_validate(manifest).model_dump(mode="json")
        if supplied != builtin or supplied["execution_mode"] != "ILLUSTRATIVE":
            raise ValueError("This adapter only implements the bundled illustrative capabilities")
        if supplied["engine_name"] != self.ENGINE_NAME or supplied["engine_version"] != self.ENGINE_VERSION:
            raise ValueError("Adapter identity and manifest disagree")
        if supplied["physiology_engine_verified"]:
            raise ValueError("Illustrative output cannot claim verified physiology")
        self._manifest = supplied
        self._manifest_hash = hashlib.sha256(_canonical(supplied).encode()).hexdigest()
        self.simulation_time = 0.0
        self.sequence = 0
        self.is_initialized = False
        self.profile = {}
        self.assumptions = {}
        self.active_events = []
        self.state = copy.deepcopy(self.BASELINE)

    def capabilities(self) -> Dict[str, Any]:
        return copy.deepcopy(self._manifest)

    def initialize(self, profile: Dict[str, Any], assumptions: Optional[Dict[str, Any]] = None) -> bool:
        # Validate/copy before committing initialization, so rejection is atomic.
        copied_profile = json.loads(_canonical(profile))
        copied_assumptions = json.loads(_canonical(assumptions or {}))
        if not isinstance(copied_profile, dict) or not isinstance(copied_assumptions, dict):
            raise ValueError("Profile and assumptions must be objects")
        self.profile = copied_profile
        self.assumptions = copied_assumptions
        self.state = copy.deepcopy(self.BASELINE)
        self.simulation_time = 0.0
        self.sequence = 0
        self.active_events = []
        self.is_initialized = True
        return True

    def _volume_at(self, when: float, events: list) -> float:
        amounts = [self.BASELINE["total_fluid_volume"]]
        for event in events:
            if not event.get("numerical_applied"):
                continue
            elapsed = when - event["started_at"]
            if elapsed < 0:
                continue
            fraction = min(elapsed / event["duration"], 1.0) if event["duration"] else 1.0
            amounts.append(event["fluid_delta_liters"] * fraction)
        return math.fsum(amounts)

    def apply_event(self, event: Dict[str, Any]) -> bool:
        if not self.is_initialized:
            raise RuntimeError("Initialize the adapter before applying an action")
        ingredient = event.get("ingredient_id") or event.get("name") or event.get("type") or ""
        action = canonical_identifier(ingredient, INTERVENTION_ALIASES, self._manifest["interventions"])
        if action is None or self._manifest["interventions"][action]["capability"] == "unsupported":
            return False
        dose = _number(event.get("dose"), "dose")
        duration = _number(event.get("duration", 0), "duration")
        when = _number(event.get("simulation_time", self.simulation_time), "simulation_time")
        if when != self.simulation_time:
            raise ValueError("An action must be applied at its scheduled engine time")
        completion = when + duration
        if duration > 0 and (not math.isfinite(completion) or completion <= when):
            raise ValueError("Action duration has no finite representable completion time")
        copied = json.loads(_canonical(event))
        copied.update(started_at=self.simulation_time, duration=duration, canonical_action=action,
                      numerical_applied=False, capability_status="evidence_only")
        copied.pop("fluid_delta_liters", None)
        if action in ("Dehydration", "IV_Saline_Infusion"):
            expected_route = "environmental" if action == "Dehydration" else "intravenous"
            if event.get("route") != expected_route:
                raise ValueError(f"{action} requires route {expected_route}")
            unit = event.get("unit")
            if unit == "mL":
                liters = dose / 1000
            elif unit == "L":
                liters = dose
            elif action == "Dehydration" and unit == "fraction" and dose <= 1:
                liters = self._volume_at(self.simulation_time, self.active_events) * dose
            else:
                raise ValueError("Fluid amount requires mL/L, or dehydration fraction in [0,1]")
            copied.update(numerical_applied=True, capability_status="illustrative",
                          fluid_delta_liters=-liters if action == "Dehydration" else liters)
        else:
            if event.get("unit") not in ("mg", "g") or event.get("route") not in ("oral", "intravenous", "rectal", "intramuscular"):
                raise ValueError("Evidence exposure requires an explicit supported dose unit and route")
        candidate = self.active_events + [copied]
        # Fluid schedules have piecewise-linear slopes. Check every future knot
        # before accepting; do not hide excessive removal behind a clamp.
        knots = [self.simulation_time] + [e["started_at"] + e["duration"] for e in candidate]
        if any(not math.isfinite(self._volume_at(t, candidate)) or self._volume_at(t, candidate) < 0 for t in knots):
            raise ValueError("Fluid schedule would produce invalid total volume")
        self.active_events = candidate
        self.state["total_fluid_volume"] = self._volume_at(self.simulation_time, candidate)
        return True

    def advance(self, delta_seconds: float) -> bool:
        if not self.is_initialized:
            raise RuntimeError("Initialize the adapter before advancing")
        delta = _number(delta_seconds, "delta_seconds")
        next_time = self.simulation_time + delta
        volume = self._volume_at(next_time, self.active_events)
        if not math.isfinite(next_time) or (delta > 0 and next_time <= self.simulation_time) or not math.isfinite(volume) or volume < 0:
            raise ValueError("Advance would produce invalid time or total fluid")
        self.simulation_time = next_time
        self.state["total_fluid_volume"] = volume
        self.sequence += 1
        return True

    def snapshot(self) -> Dict[str, Any]:
        if not self.is_initialized:
            raise RuntimeError("Initialize the adapter before taking a snapshot")
        valid = all(math.isfinite(v) for v in self.state.values()) and self.state["total_fluid_volume"] >= 0
        return {
            "run_id": self.profile.get("run_id", "local_run"), "sequence": self.sequence,
            "simulation_time": self.simulation_time,
            "quantities": {k: {"value": v, "unit": self._manifest["metrics"][k]["unit"],
                               "source": "pdtt_illustrative_model", "capability": "illustrative"}
                           for k, v in self.state.items()},
            "coverage_flags": {
                "execution_mode": "ILLUSTRATIVE", "engine_simulated": False,
                "physiology_engine_verified": False, "evidence_verified": False,
                "patient_prediction": False, "model_baseline": "Fixed educational constants; not patient measurements",
                "model_assumptions": copy.deepcopy(self.BASELINE),
                "context_only_conditions": copy.deepcopy(self.profile.get("conditions", [])),
                "context_only_fields": sorted(self.profile.get("context", {})),
                "ignored_baseline_inputs": sorted(self.profile.get("baseline_measurements", {})),
                "ignored_profile_inputs": [k for k in ("age", "sex", "mass_kg", "current_medications", "allergies") if k in self.profile],
                "unsupported_quantities": sorted(k for k, v in self._manifest["metrics"].items() if v["capability"] == "unsupported"),
                "evidence_only_interventions": [e.get("ingredient_id") or e.get("name") or e["canonical_action"]
                                                for e in self.active_events if not e["numerical_applied"]],
                "limitations": list(self._manifest["limitations"]),
            },
            "is_valid": valid, "numerical_error_code": None if valid else "INVALID_ILLUSTRATIVE_STATE",
        }

    def serialize(self) -> str:
        if not self.is_initialized:
            raise RuntimeError("Initialize before creating a checkpoint")
        payload = {
            "schema_version": "2.0.0", "engine_name": self.ENGINE_NAME,
            "engine_version": self.ENGINE_VERSION, "execution_mode": "ILLUSTRATIVE",
            "manifest_hash": self._manifest_hash, "simulation_time": self.simulation_time,
            "sequence": self.sequence, "profile": self.profile, "assumptions": self.assumptions,
            "state": self.state, "active_events": self.active_events,
        }
        return _canonical({"payload": payload, "content_hash": hashlib.sha256(_canonical(payload).encode()).hexdigest()})

    def restore(self, checkpoint: str) -> bool:
        envelope = json.loads(checkpoint)
        if set(envelope) != {"payload", "content_hash"}:
            raise ValueError("Unsupported checkpoint envelope")
        data = envelope["payload"]
        if hashlib.sha256(_canonical(data).encode()).hexdigest() != envelope["content_hash"]:
            raise ValueError("Checkpoint content hash mismatch")
        expected = {"schema_version": "2.0.0", "engine_name": self.ENGINE_NAME,
                    "engine_version": self.ENGINE_VERSION, "execution_mode": "ILLUSTRATIVE",
                    "manifest_hash": self._manifest_hash}
        if any(data.get(k) != v for k, v in expected.items()):
            raise ValueError("Checkpoint engine/schema/capability version is incompatible")
        when = _number(data["simulation_time"], "simulation_time")
        if isinstance(data["sequence"], bool) or not isinstance(data["sequence"], int) or data["sequence"] < 0:
            raise ValueError("Invalid checkpoint sequence")
        # Rebuild and validate actions before replacing any live state.
        candidate = IllustrativeEngineAdapter(self._manifest)
        candidate.initialize(data["profile"], data["assumptions"])
        for event in data["active_events"]:
            start = _number(event["started_at"], "started_at")
            if start < candidate.simulation_time or start > when:
                raise ValueError("Checkpoint contains an invalid action schedule")
            candidate.advance(start - candidate.simulation_time)
            if not candidate.apply_event(event):
                raise ValueError("Checkpoint contains an unsupported action")
        candidate.advance(when - candidate.simulation_time)
        if candidate.state != data["state"] or candidate.active_events != data["active_events"]:
            raise ValueError("Checkpoint state does not agree with its admitted actions")
        candidate.sequence = data["sequence"]
        self.profile, self.assumptions = candidate.profile, candidate.assumptions
        self.active_events, self.state = candidate.active_events, candidate.state
        self.simulation_time, self.sequence = candidate.simulation_time, candidate.sequence
        self.is_initialized = True
        return True


# Compatibility for existing callers; the implementation and all provenance are
# explicitly illustrative. No reference replay is provided by this legacy name.
ReferenceTraceEngineAdapter = IllustrativeEngineAdapter
