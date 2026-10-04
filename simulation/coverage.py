"""Scenario coverage from the active adapter's strict capability manifest."""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from simulation.capabilities import (
    CapabilityLevel, CapabilityManifest, CONDITION_ALIASES, INTERVENTION_ALIASES,
    canonical_identifier, load_manifest,
)


class ScenarioCoverageReport(BaseModel):
    is_runnable: bool
    overall_status: str
    execution_mode: str
    physiology_engine_verified: bool
    simulated_aspects: List[str] = Field(default_factory=list)
    illustrative_aspects: List[str] = Field(default_factory=list)
    evidence_only_aspects: List[str] = Field(default_factory=list)
    unsupported_aspects: List[str] = Field(default_factory=list)
    context_only_aspects: List[str] = Field(default_factory=list)
    missing_measurements: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class CoverageGate:
    CONDITION_ALIASES = CONDITION_ALIASES
    INTERVENTION_ALIASES = INTERVENTION_ALIASES

    def __init__(self, manifest_path: Optional[str] = None, manifest: Optional[Dict[str, Any]] = None):
        if manifest_path is not None and manifest is not None:
            raise ValueError("Provide a manifest or a path, not both")
        self.manifest_path = manifest_path
        self._manifest = (CapabilityManifest.model_validate(manifest) if manifest is not None else load_manifest(manifest_path)).model_dump(mode="json")
        self.metrics = self._manifest["metrics"]
        self.conditions = self._manifest["conditions"]
        self.interventions = self._manifest["interventions"]

    def _load_manifest(self, path: str) -> Dict[str, Any]:
        return load_manifest(path).model_dump(mode="json")

    def evaluate_metric(self, metric_name: str) -> CapabilityLevel:
        key = canonical_identifier(metric_name, {}, self.metrics)
        return CapabilityLevel(self.metrics[key]["capability"]) if key else CapabilityLevel.UNSUPPORTED

    def evaluate_condition(self, condition_name: str) -> CapabilityLevel:
        key = canonical_identifier(condition_name, self.CONDITION_ALIASES, self.conditions)
        return CapabilityLevel(self.conditions[key]["capability"]) if key else CapabilityLevel.UNSUPPORTED

    def evaluate_intervention(self, intervention_name: str) -> Dict[str, Any]:
        key = canonical_identifier(intervention_name, self.INTERVENTION_ALIASES, self.interventions)
        if key:
            details = self.interventions[key]
            return {"name": details["name"], "canonical_id": key,
                    "capability": CapabilityLevel(details["capability"]),
                    "numerical_effect": details["numerical_effect"],
                    "evidence_effect": details["evidence_effect"],
                    "evidence_verified": self._manifest["evidence_verified"],
                    "target_organs": details["target_organs"], "notes": details.get("notes") or ""}
        return {"name": intervention_name, "canonical_id": None,
                "capability": CapabilityLevel.UNSUPPORTED, "numerical_effect": False,
                "evidence_effect": False, "evidence_verified": False,
                "target_organs": [], "notes": "Not implemented by the active adapter or evidence registry."}

    def validate_scenario(self, profile: Union[Dict[str, Any], Any], interventions: List) -> ScenarioCoverageReport:
        p = profile.model_dump() if hasattr(profile, "model_dump") else profile
        report = ScenarioCoverageReport(
            is_runnable=True, overall_status="illustrative", execution_mode=self._manifest["execution_mode"],
            physiology_engine_verified=self._manifest["physiology_engine_verified"],
            limitations=list(self._manifest["limitations"]),
        )
        buckets = {CapabilityLevel.ENGINE_SIMULATED: report.simulated_aspects,
                   CapabilityLevel.ILLUSTRATIVE: report.illustrative_aspects,
                   CapabilityLevel.EVIDENCE_ONLY: report.evidence_only_aspects,
                   CapabilityLevel.UNSUPPORTED: report.unsupported_aspects}
        conditions = p.get("conditions", [])
        for name in conditions:
            capability = self.evaluate_condition(name)
            buckets[capability].append(f"Condition: {name}")
            report.context_only_aspects.append(f"Condition: {name}")
        context = p.get("context", {})
        for name, value in context.items():
            report.context_only_aspects.append(f"Context: {name}={value}")
        if context.get("diabetes") in (True, "true"):
            report.warnings.append("Diabetes is context only. Glucose, nephropathy and measured renal function are not generated.")
        measurements = p.get("baseline_measurements", {})
        for name, measurement in measurements.items():
            m = measurement.model_dump() if hasattr(measurement, "model_dump") else measurement
            if m.get("is_missing") or m.get("value") is None:
                report.missing_measurements.append(name)
        renal_keys = {canonical_identifier(c, CONDITION_ALIASES, self.conditions) for c in conditions}
        if renal_keys.intersection({"CKD", "ChronicRenalStenosis"}) or context.get("diabetes") in (True, "true"):
            for label, names in [("eGFR (Glomerular Filtration Rate)", ("egfr", "glomerular_filtration_rate")),
                                 ("Serum Creatinine", ("creatinine", "serum_creatinine"))]:
                provided = [measurements[n] for n in names if n in measurements]
                if not any(m.get("value") is not None and not m.get("is_missing") for m in provided):
                    report.missing_measurements.append(label)
            report.warnings.append("Missing renal measurements remain missing; educational model constants are not patient labs.")
        if measurements:
            report.warnings.append("Supplied baseline measurements are retained separately and are not applied by the illustrative adapter.")
        for intervention in interventions:
            i = intervention.model_dump() if hasattr(intervention, "model_dump") else intervention
            name = i.get("ingredient_id") or i.get("name") or i.get("type") or "Unknown"
            result = self.evaluate_intervention(name)
            capability = result["capability"]
            buckets[capability].append(f"Intervention: {result['name']}")
            if capability == CapabilityLevel.UNSUPPORTED:
                report.is_runnable = False
                report.warnings.append(f"Intervention '{name}' is not executable in this adapter.")
            elif capability == CapabilityLevel.EVIDENCE_ONLY:
                report.warnings.append(f"Intervention '{result['name']}' has no numerical model; qualitative rule applicability and evidence review are separate.")
            elif capability == CapabilityLevel.ILLUSTRATIVE:
                report.warnings.append(f"Intervention '{result['name']}' changes illustrative fluid bookkeeping only, not predicted organ function.")
        if not self._manifest["evidence_verified"]:
            report.warnings.append("Evidence source/rule verification is pending; no clinical review or safe-treatment conclusion is established.")
        if report.unsupported_aspects:
            report.overall_status = "unsupported_elements_present"
        elif self._manifest["execution_mode"] == "ILLUSTRATIVE":
            report.overall_status = "illustrative_with_evidence" if report.evidence_only_aspects else "illustrative"
        else:
            report.overall_status = "hybrid_evidence_supported" if report.evidence_only_aspects else "fully_simulated"
        report.missing_measurements = list(dict.fromkeys(report.missing_measurements))
        return report
