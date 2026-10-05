"""Per-organ assessment coverage for a report's pinned medication basis."""

ORGANS = ("cardiovascular", "respiratory", "renal", "hepatic")


def build_organ_coverage(drugs: dict, rules: dict, capabilities: dict,
                         verified_outputs: set[tuple[str, str, str]] | None = None) -> dict:
    interventions = capabilities.get("interventions", {})
    verified_outputs = verified_outputs or set()
    result = {}
    for drug_id, drug in drugs.items():
        intervention = interventions.get(drug_id, {})
        result[drug_id] = {}
        for organ in ORGANS:
            reviewed = sorted(rule_id for rule_id, rule in rules.items()
                              if rule.get("review_status") == "reviewed"
                              and rule.get("ingredient_or_class") == drug_id
                              and rule.get("target_organ") == organ)
            declared_model = intervention.get("numerical_model_id")
            model_id = (declared_model if intervention.get("numerical_effect")
                        and organ in intervention.get("numerical_organs", [])
                        and (drug_id, organ, declared_model) in verified_outputs else None)
            result[drug_id][organ] = {
                "associated": organ in drug.get("target_organs", []),
                "reviewed_rule_ids": reviewed,
                "numerical_model_id": model_id,
                "numerical_status": "engine_simulated" if model_id else "unsupported",
            }
    return result
