"""Four read-only organ observers, joined by a deterministic LangGraph barrier."""
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from backend.evidence.registry import EvidenceRegistry
from backend.schemas.domain import DraftFinding, Intervention, PatientProfile, PhysiologySnapshot

ORGANS = ("renal", "cardiovascular", "hepatic", "respiratory")


class CouncilState(TypedDict, total=False):
    profile: PatientProfile
    snapshot: PhysiologySnapshot
    active_interventions: tuple[Intervention, ...]
    renal: tuple[DraftFinding, ...]
    cardiovascular: tuple[DraftFinding, ...]
    hepatic: tuple[DraftFinding, ...]
    respiratory: tuple[DraftFinding, ...]
    findings: tuple[DraftFinding, ...]


class OrganCouncil:
    """No node owns or edits physiological quantities; the worker owns time."""
    def __init__(self, registry: EvidenceRegistry | None = None):
        self.registry = registry or EvidenceRegistry()
        builder = StateGraph(CouncilState)
        for organ in ORGANS:
            builder.add_node(organ, self._observer(organ))
            builder.add_edge(START, organ)
        builder.add_node("consistency", self._consistency)
        builder.add_edge(list(ORGANS), "consistency")
        builder.add_edge("consistency", END)
        self.graph = builder.compile()

    def _observer(self, organ: str):
        def observe(state: CouncilState):
            profile = state["profile"]
            snapshot = state["snapshot"]
            active = state["active_interventions"]
            evidence = [item for item in self.registry.evaluate_rules(profile, snapshot, list(active))
                        if item.organ == organ]
            drafts = []
            for item in evidence:
                drafts.append(DraftFinding(
                    run_id=snapshot.run_id, source_snapshot_sequence=snapshot.sequence,
                    simulation_time=snapshot.simulation_time, organ=organ,
                    category=item.category, severity=item.severity,
                    inputs_observed=item.inputs_observed,
                    predicate_outcomes=item.predicate_outcomes,
                    missing_inputs=tuple(item.missing_inputs), rule_id=item.rule_id,
                    evidence_ids=tuple(item.evidence_ids),
                    source_versions=item.source_versions,
                    coverage=item.coverage, message=item.message,
                    limitations=item.limitations,
                    causal_event_ids=tuple(item.causal_event_ids),
                ))
            if not drafts:
                timeline_only = snapshot.coverage_flags.get("execution_mode") == "EVIDENCE_TIMELINE"
                drafts.append(DraftFinding(
                    run_id=snapshot.run_id, source_snapshot_sequence=snapshot.sequence,
                    simulation_time=snapshot.simulation_time, organ=organ,
                    category="physiological_response", severity="unknown",
                    inputs_observed={"snapshot_sequence": snapshot.sequence,
                                     "execution_mode": snapshot.coverage_flags.get("execution_mode", "unknown")},
                    rule_id=f"UNMODELED_{organ.upper()}", coverage="unsupported",
                    message=f"{organ.capitalize()} response is not modeled for this scenario.",
                    limitations=("Only administered amounts are calculated. No physiological baseline, organ function, or drug concentration is generated."
                                 if timeline_only else "Displayed baseline quantities are fixed illustrative constants, not patient predictions."),
                    causal_event_ids=tuple(item.event_id for item in active),
                ))
            return {organ: tuple(drafts)}
        return observe

    @staticmethod
    def _consistency(state: CouncilState):
        snapshot = state["snapshot"]
        all_findings = tuple(item for organ in ORGANS for item in state[organ])
        for item in all_findings:
            if (item.run_id != snapshot.run_id or
                item.source_snapshot_sequence != snapshot.sequence or
                item.simulation_time != snapshot.simulation_time):
                raise ValueError("Organ finding disagrees with immutable source snapshot")
        return {"findings": tuple(sorted(all_findings, key=lambda item:
                (ORGANS.index(item.organ), item.rule_id or "", item.category)))}

    def evaluate(self, profile: PatientProfile, snapshot: PhysiologySnapshot,
                 active_interventions: list[Intervention]) -> tuple[DraftFinding, ...]:
        profile = PatientProfile.model_validate(profile)
        snapshot = PhysiologySnapshot.model_validate(snapshot)
        active = tuple(Intervention.model_validate(item) for item in active_interventions
                       if item.simulation_time <= snapshot.simulation_time)
        result = self.graph.invoke({"profile": profile, "snapshot": snapshot,
                                    "active_interventions": active})
        return result["findings"]
