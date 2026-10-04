"""Conservative, source-linked checks for the submitted patient workflow."""
from backend.evidence.registry import EvidenceRegistry
from backend.evidence.models import EvidenceRule, EvidenceSource, Precondition


class PatientEvidenceRegistry(EvidenceRegistry):
    def __init__(self):
        super().__init__()
        self.sources = [
            EvidenceSource(source_id="NIDDK_MEDICINE", title="NIDDK: Keeping Kidneys Safe - Smart Choices about Medicines",
                url="https://www.niddk.nih.gov/health-information/kidney-disease/keeping-kidneys-safe",
                publication_date="accessed 2026-10-04", license="Refer to NIH terms",
                raw_extract="Paraphrase: NSAIDs such as ibuprofen warrant kidney-risk review in susceptible patients; no individual injury magnitude is established."),
            EvidenceSource(source_id="DAILYMED_SALINE", title="DailyMed: 0.9% Sodium Chloride Injection - Warnings",
                url="https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=d98bf9f7-30ec-4927-a577-cabad192cb18&type=display",
                publication_date="accessed 2026-10-04", license="Refer to label terms",
                raw_extract="Paraphrase: the label cautions about fluid/solute overload and use in heart failure and severe renal insufficiency."),
            EvidenceSource(source_id="DAILYMED_MORPHINE", title="DailyMed: Morphine Sulfate Tablets - Warnings and Hepatic Impairment",
                url="https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=5178907d-3695-3666-e054-00144ff88e88",
                publication_date="accessed 2026-10-04", license="Refer to label terms",
                raw_extract="Paraphrase: morphine carries respiratory-depression warnings and cirrhosis can alter its pharmacokinetics."),
        ]
        self.rules = [
            EvidenceRule(rule_id="RULE_NSAID_RENAL_HEMODYNAMIC", version="2.0.0", target_organ="renal",
                category="medication_caution", severity="monitor", ingredient_or_class="ibuprofen",
                mechanism="The source identifies ibuprofen and other NSAIDs as a kidney-risk concern in susceptible patients. Recorded history supports a qualitative caution, not a calculated fall in filtration.",
                preconditions=Precondition(required_conditions=["CKD", "ChronicRenalStenosis", "EssentialHypertension", "Type2DiabetesMellitus"], trigger_interventions=["ibuprofen"]),
                source_id="NIDDK_MEDICINE", source_section="NSAIDs and kidney disease; blood pressure and dehydration context",
                review_status="reviewed", limitations="No dose-specific injury estimate, AKI diagnosis, or eGFR trajectory is available. Missing labs limit personalization. Source-link verification is not independent clinical validation.",
                user_message="Ibuprofen was administered with recorded kidney vulnerability or related history. A source-linked kidney-risk caution applies; renal injury is not predicted."),
            EvidenceRule(rule_id="RULE_CHF_FLUID_OVERLOAD", version="2.0.0", target_organ="cardiovascular",
                category="medication_caution", severity="monitor", ingredient_or_class="saline",
                mechanism="The saline label cautions about fluid overload in patients with heart failure. The entered infusion can be recorded arithmetically, but congestion and pressure changes are not modeled.",
                preconditions=Precondition(required_conditions=["CHF", "ChronicVentricularSystolicDysfunction"], trigger_interventions=["saline"]),
                source_id="DAILYMED_SALINE", source_section="Warnings: fluid/solute overload and congestive heart failure",
                review_status="reviewed", limitations="No pulmonary edema, pressure, fluid-distribution, or clinical outcome prediction is available.",
                user_message="Saline administration with recorded heart failure merits fluid-status review. This assessment does not predict overload or decompensation."),
            EvidenceRule(rule_id="RULE_OPIOID_HEPATIC_RESPIRATORY", version="2.0.0", target_organ="hepatic",
                category="medication_caution", severity="monitor", ingredient_or_class="morphine",
                mechanism="The morphine label describes altered pharmacokinetics in cirrhosis. A recorded cirrhosis history supports a clearance-related caution without a patient-specific half-life estimate.",
                preconditions=Precondition(required_conditions=["HepaticCirrhosis"], trigger_interventions=["morphine"]),
                source_id="DAILYMED_MORPHINE", source_section="Use in Specific Populations: Hepatic Impairment",
                review_status="reviewed", limitations="Clearance, concentration, dose suitability, and the degree of accumulation are unavailable. The cited tablet label does not validate all formulations/routes.",
                user_message="Morphine administration with recorded cirrhosis merits hepatic-clearance review. The degree or duration of accumulation cannot be calculated."),
            EvidenceRule(rule_id="RULE_MORPHINE_RESPIRATORY", version="1.0.0", target_organ="respiratory",
                category="medication_caution", severity="monitor", ingredient_or_class="morphine",
                mechanism="The morphine label warns about respiratory depression. This is a labeled hazard to review, not evidence that this patient has developed hypoventilation.",
                preconditions=Precondition(trigger_interventions=["morphine"]),
                source_id="DAILYMED_MORPHINE", source_section="Warnings and Precautions: Life-Threatening Respiratory Depression",
                review_status="reviewed", limitations="Breathing rate, oxygenation, duration, and likelihood of respiratory depression are not predicted.",
                user_message="Morphine has a labeled respiratory-depression hazard. Review the patient's breathing context; no respiratory effect is numerically predicted."),
        ]

    def evaluate_rules(self, profile, snapshot, active_interventions):
        findings = super().evaluate_rules(profile, snapshot, active_interventions)
        active = [item for item in active_interventions if item.simulation_time <= snapshot.simulation_time]
        from backend.schemas.domain import AgentFinding
        from backend.catalogue.registry import drugs_by_id
        drugs = drugs_by_id()
        for item in active:
            if item.ingredient_id not in drugs:
                continue
            matches = [allergen for allergen in profile.allergies if allergen.casefold() in
                       (item.ingredient_id.casefold(), drugs[item.ingredient_id]["name"].casefold())]
            if matches:
                organ = drugs[item.ingredient_id]["target_organs"][0]
                findings.append(AgentFinding(finding_id=f"{snapshot.run_id}:allergy:{item.ingredient_id}:{snapshot.sequence}",
                    run_id=snapshot.run_id, sequence=snapshot.sequence, source_snapshot_sequence=snapshot.sequence,
                    simulation_time=snapshot.simulation_time, organ=organ, category="reported_allergy_overlap",
                    severity="monitor", coverage="evidence_only", rule_id="ALLERGY_EXACT_INGREDIENT",
                    inputs_observed={"reported_allergy": ", ".join(matches), "ingredient": item.ingredient_id},
                    predicate_outcomes={"exact_ingredient_match": True}, causal_event_ids=[item.event_id],
                    message="An administered ingredient exactly matches the recorded allergy list. Clinical review is required.",
                    limitations="Exact text match only. Cross-reactivity, reactions, brands, and related ingredients are not assessed."))
        return findings
