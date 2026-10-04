"""Qualitative source-linked checks, never numerical drug-response predictions."""
import json
from pathlib import Path
from typing import List

from backend.evidence.models import EvidenceRule, EvidenceSource
from backend.schemas.domain import PatientProfile, PhysiologySnapshot, Intervention, AgentFinding
from simulation.capabilities import CONDITION_ALIASES, INTERVENTION_ALIASES, canonical_identifier


def _canonical(value, aliases):
    return canonical_identifier(value, aliases, set(aliases.values())) or value


class EvidenceRegistry:
    def __init__(self, writer=None):
        base = Path(__file__).parent
        self.rules: List[EvidenceRule] = [EvidenceRule.model_validate(item) for item in
            json.loads((base / "rules.json").read_text(encoding="utf-8"))]
        self.sources: List[EvidenceSource] = [EvidenceSource.model_validate(item) for item in
            json.loads((base / "sources.json").read_text(encoding="utf-8"))]
        self.writer = writer

    def evaluate_rules(self, profile: PatientProfile, snapshot: PhysiologySnapshot,
                       active_interventions: List[Intervention]) -> List[AgentFinding]:
        profile = PatientProfile.model_validate(profile)
        snapshot = PhysiologySnapshot.model_validate(snapshot)
        active = [Intervention.model_validate(item) for item in active_interventions
                  if item.simulation_time <= snapshot.simulation_time]
        active_ids = {_canonical(item.ingredient_id, INTERVENTION_ALIASES) for item in active}
        conditions = {_canonical(item, CONDITION_ALIASES) for item in profile.conditions}
        known_sources = {source.source_id for source in self.sources}
        results = []

        for rule in self.rules:
            if rule.review_status != "reviewed" or rule.source_id not in known_sources:
                continue
            triggers = {_canonical(item, INTERVENTION_ALIASES)
                        for item in rule.preconditions.trigger_interventions}
            if triggers and not (triggers & active_ids):
                continue

            outcomes = {}
            missing = []
            matched_condition = any(_canonical(item, CONDITION_ALIASES) in conditions
                                    for item in rule.preconditions.required_conditions)
            outcomes["condition"] = matched_condition
            matched_context = False
            severe_unstudied = False
            for key, expected in rule.preconditions.required_context.items():
                observed = profile.context.get(key)
                if observed == expected:
                    matched_context = True
                elif key == "hepatic_impairment" and expected == "moderate" and observed == "severe":
                    matched_context = True
                    severe_unstudied = True
            outcomes["context"] = matched_context

            matched_threshold = False
            for metric, limits in rule.preconditions.hemodynamic_thresholds.items():
                quantity = snapshot.quantities.get(metric)
                if quantity is None or quantity.capability != "engine_simulated":
                    missing.append(metric)
                    outcomes[metric] = "not clinically modeled"
                    continue
                value = quantity.value
                hit = (("max" in limits and value <= limits["max"]) or
                       ("min" in limits and value >= limits["min"]))
                outcomes[metric] = hit
                matched_threshold |= hit

            criteria = bool(rule.preconditions.required_conditions or
                            rule.preconditions.required_context or
                            rule.preconditions.hemodynamic_thresholds)
            vulnerable = not criteria or matched_condition or matched_context or matched_threshold
            if not vulnerable and not missing:
                continue
            for name in rule.preconditions.required_measurements:
                measured = profile.baseline_measurements.get(name)
                if measured is None or measured.is_missing or measured.value is None:
                    missing.append(name)

            required_missing = any(name in rule.preconditions.required_measurements for name in missing)
            severity = "unknown" if ((not vulnerable and missing) or required_missing or severe_unstudied) else rule.severity
            coverage = "unsupported" if severity == "unknown" else "evidence_only"
            if severe_unstudied:
                message = "Severe hepatic impairment: this rule cannot assess the degree of morphine accumulation. Review the source and patient data."
            elif severity == "unknown":
                label = "Missing required baseline measurements" if required_missing else "Missing required observed inputs"
                message = f"{label}: {', '.join(sorted(set(missing)))}. Cannot evaluate risk."
            else:
                message = rule.user_message
            observed = {"active_ingredients": ", ".join(sorted(active_ids)),
                        "conditions": ", ".join(sorted(conditions))}
            observed.update({name: snapshot.quantities[name].value
                             for name in rule.preconditions.hemodynamic_thresholds
                             if name in snapshot.quantities and
                             snapshot.quantities[name].capability == "engine_simulated"})
            results.append(AgentFinding(
                finding_id=f"{snapshot.run_id}:{rule.rule_id}:{snapshot.sequence}",
                run_id=snapshot.run_id, sequence=snapshot.sequence,
                source_snapshot_sequence=snapshot.sequence,
                simulation_time=snapshot.simulation_time, organ=rule.target_organ,
                category=rule.category, severity=severity, inputs_observed=observed,
                predicate_outcomes=outcomes, missing_inputs=sorted(set(missing)),
                rule_id=rule.rule_id, evidence_ids=[rule.source_id],
                source_versions={rule.source_id: rule.version},
                coverage=coverage, message=message, limitations=rule.limitations,
                causal_event_ids=[item.event_id for item in active
                                  if _canonical(item.ingredient_id, INTERVENTION_ALIASES) in triggers],
            ))
        return results
