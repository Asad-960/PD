"""Patient-level exact ingredient allergy alerts from applied administrations."""


def build_safety_alerts(intake, administrations: list[dict], drugs: dict) -> list[dict]:
    alerts = []
    for action in administrations:
        drug_id = action["ingredient_id"]
        drug = drugs.get(drug_id)
        if not drug:
            continue
        names = {drug_id.casefold(), drug["name"].casefold()}
        for allergy in intake.patient.allergies:
            if allergy.casefold() in names:
                alerts.append({"event_id": action["event_id"],
                               "time": action["simulation_time"],
                               "ingredient_id": drug_id,
                               "reported_allergy": allergy})
                break
    return alerts
