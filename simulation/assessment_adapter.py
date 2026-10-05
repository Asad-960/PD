"""An administration ledger, not a physiological or pharmacokinetic model."""
import copy
import hashlib
import json
import math

from backend.catalogue.registry import conditions_by_id, drugs_by_id
from simulation.adapter import PhysiologyEngineAdapter
from simulation.capabilities import CapabilityManifest


class AssessmentTimelineAdapter(PhysiologyEngineAdapter):
    ENGINE_NAME = "PDTT Evidence and Administration Timeline"
    ENGINE_VERSION = "1.0.0"

    def __init__(self):
        self.drugs = drugs_by_id()
        self.profile = {}
        self.assumptions = {}
        self.events = []
        self.simulation_time = 0.0
        self.initialized = False
        self._manifest = {
            "schema_version": "1.0.0", "engine_name": self.ENGINE_NAME,
            "engine_version": self.ENGINE_VERSION, "engine_available_locally": True,
            "execution_mode": "ILLUSTRATIVE", "physiology_engine_verified": False,
            "evidence_verified": False,
            "provenance_statement": "Deterministic administration amounts and source-linked evidence; no numerical physiology or drug concentrations.",
            "limitations": ["Patient-specific organ responses and drug interactions are not numerically modeled.",
                "Recorded doses are not concentrations, absorption, clearance, or therapeutic effect.",
                "Clinical validation and independent evidence review have not been established."],
            "metrics": {"administered_" + key: {"name": "administered_" + key,
                "display_name": drug["name"] + " administered", "unit": "mL" if key == "saline" else "mg",
                "domain": "administration", "capability": "illustrative",
                "description": "Cumulative administered amount from the submitted schedule.",
                "notes": "Arithmetic ledger only; not blood concentration."} for key, drug in self.drugs.items()},
            "conditions": {item["canonical_id"]: {"name": item["name"], "engine_mapping": None,
                "capability": "unsupported", "target_organs": [item["organ"]],
                "notes": "History context only; disease-specific physiological response is unavailable."}
                for item in conditions_by_id().values()},
            "interventions": {key: {"name": drug["name"], "ingredient_or_type": key,
                "route": None, "capability": "evidence_only", "target_organs": drug["target_organs"],
                "numerical_effect": False, "evidence_effect": drug["evidence_available"],
                "notes": drug["rule_scope"]} for key, drug in self.drugs.items()},
        }
        self._manifest = CapabilityManifest.model_validate(self._manifest).model_dump(mode="json")

    def capabilities(self):
        return copy.deepcopy(self._manifest)

    def initialize(self, profile, assumptions=None):
        self.profile = json.loads(json.dumps(profile, allow_nan=False))
        self.assumptions = json.loads(json.dumps(assumptions or {}, allow_nan=False))
        self.events, self.simulation_time = [], 0.0
        self.initialized = True
        return True

    def apply_event(self, event):
        if not self.initialized:
            raise RuntimeError("Initialize before recording an administration")
        key = event.get("ingredient_id")
        if key not in self.drugs:
            return False
        unit = "mL" if key == "saline" else "mg"
        dose, duration = event.get("dose"), event.get("duration", 0)
        if (type(dose) not in (int, float) or not math.isfinite(dose) or dose <= 0 or
                type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0 or
                event.get("unit") != unit or event.get("route") not in self.drugs[key]["routes"] or
                event.get("simulation_time") != self.simulation_time):
            raise ValueError("Invalid normalized administration")
        if not math.isfinite(self.simulation_time + duration):
            raise ValueError("Invalid administration completion time")
        self.events.append(copy.deepcopy(event))
        return True

    def advance(self, delta_seconds):
        if not self.initialized or type(delta_seconds) not in (int, float) or not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("Advance requires an initialized timeline and a finite nonnegative interval")
        next_time = self.simulation_time + delta_seconds
        if not math.isfinite(next_time) or (delta_seconds > 0 and next_time <= self.simulation_time):
            raise ValueError("Invalid timeline advancement")
        self.simulation_time = next_time
        return True

    def snapshot(self):
        if not self.initialized:
            raise RuntimeError("Initialize before snapshot")
        names = {m["drug_id"] for m in self.profile.get("intake", {}).get("medications", [])}
        quantities = {}
        for name in names:
            amounts = []
            for event in self.events:
                if event["ingredient_id"] != name:
                    continue
                elapsed = self.simulation_time - event["simulation_time"]
                duration = event.get("duration", 0)
                fraction = max(0, min(1, elapsed / duration)) if duration else 1
                amounts.append(event["dose"] * fraction)
            quantities["administered_" + name] = {"value": math.fsum(amounts),
                "unit": "mL" if name == "saline" else "mg", "source": "pdtt_administration_ledger",
                "capability": "illustrative"}
        return {"run_id": self.profile.get("patient_id", "timeline"), "sequence": 0,
            "simulation_time": self.simulation_time, "quantities": quantities, "is_valid": True,
            "coverage_flags": {"execution_mode": "EVIDENCE_TIMELINE", "patient_prediction": False,
                "physiology_engine_verified": False, "evidence_verified": False,
                "limitations": self._manifest["limitations"], "conceptual_animation": True}}

    def serialize(self):
        payload = {"engine": self.ENGINE_NAME, "version": self.ENGINE_VERSION,
            "profile": self.profile, "assumptions": self.assumptions, "events": self.events, "time": self.simulation_time}
        raw = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":"))
        return json.dumps({"payload": payload, "sha256": hashlib.sha256(raw.encode()).hexdigest()})

    def restore(self, checkpoint):
        envelope = json.loads(checkpoint)
        payload = envelope["payload"]
        raw = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":"))
        if envelope["sha256"] != hashlib.sha256(raw.encode()).hexdigest() or payload["engine"] != self.ENGINE_NAME or payload["version"] != self.ENGINE_VERSION:
            raise ValueError("Incompatible or altered timeline checkpoint")
        candidate = AssessmentTimelineAdapter()
        candidate.initialize(payload["profile"], payload["assumptions"])
        for event in payload["events"]:
            candidate.advance(event["simulation_time"] - candidate.simulation_time)
            if not candidate.apply_event(event):
                raise ValueError("Unknown checkpoint medication")
        candidate.advance(payload["time"] - candidate.simulation_time)
        self.profile, self.assumptions, self.events = candidate.profile, candidate.assumptions, candidate.events
        self.simulation_time, self.initialized = candidate.simulation_time, True
        return True
