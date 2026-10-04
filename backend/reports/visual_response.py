"""Deterministic scene cues derived from recorded inputs, not physiology estimates."""

PATTERNS = {
    "cardiovascular": (
        ("arrhythmia|atrial fibrillation", "irregular_rhythm", "Irregular contraction pattern"),
        ("heart failure|low output|cardiogenic|tamponade", "reduced_contraction", "Reduced contraction pattern"),
        ("hypertension|atheroscl|stenosis", "vascular_tension", "Vessel tension pattern"),
    ),
    "renal": (
        ("obstruct|stone|hydronephrosis|postrenal", "outflow_obstruction", "Urine flow obstruction pattern"),
        ("perfusion|stenosis|ischemia|shock|dehydration", "reduced_perfusion", "Reduced perfusion pattern"),
        ("inflamm|nephritis|infection|immune", "inflammation", "Inflammation pattern"),
        ("ckd|failure|scarring|fibrosis|dysplasia", "structural_change", "Structural change pattern"),
    ),
    "hepatic": (
        ("cirrhosis|fibrosis|portal", "fibrotic_texture", "Fibrotic texture pattern"),
        ("hepatitis|inflamm|injury|failure", "inflammation", "Inflammation pattern"),
        ("ascites|congestion|hydrothorax", "congestion", "Congestion pattern"),
    ),
    "respiratory": (
        ("copd|emphysema|airway obstruction|bronchoconstriction|asthma", "restricted_airflow", "Restricted airflow pattern"),
        ("fibrosis|interstitial|ards", "restricted_expansion", "Restricted expansion pattern"),
        ("edema|pneumonia|infection|sepsis", "fluid_inflammation", "Fluid or inflammation pattern"),
        ("hypoxia|hypoxemia|depression|failure", "reduced_ventilation", "Reduced ventilation pattern"),
    ),
}


def pattern_for(organ, names):
    import re

    text = " ".join(names).lower()
    for expression, pattern, label in PATTERNS[organ]:
        if re.search(expression, text):
            return pattern, label
    return ("condition_present", "Recorded condition pattern") if names else ("resting_cycle", "Resting anatomical cycle")


def build_visual_responses(intake, conditions, drugs, administrations, findings_timeline):
    response = {}
    for organ, history in intake.organs.items():
        entries = [conditions[item.condition_id] for item in history.conditions]
        pattern, label = pattern_for(organ, [entry["name"] + " " + (entry.get("mechanism") or "") for entry in entries])
        cautions = [item for item in findings_timeline if item["organ"] == organ and item["coverage"] == "evidence_only"]
        cues = []
        for action in administrations:
            drug = drugs[action["ingredient_id"]]
            if organ not in drug["target_organs"]:
                continue
            related = [item for item in cautions if action["event_id"] in item.get("causal_event_ids", [])]
            cues.append({"time": action["simulation_time"], "event_id": action["event_id"],
                         "drug_id": action["ingredient_id"], "drug_name": drug["name"],
                         "kind": "source_linked_caution" if related else "exposure_only",
                         "rule_ids": sorted({item["rule_id"] for item in related if item.get("rule_id")})})
        response[organ] = {"pattern": pattern, "pattern_label": label,
            "condition_mechanisms": [{"condition_id": item.condition_id,
                "condition_name": conditions[item.condition_id]["name"],
                "description": conditions[item.condition_id].get("mechanism") or
                    "A condition is recorded; no specific visual mechanism was supplied.",
                "severity": item.severity,
                "references": conditions[item.condition_id]["references"]} for item in history.conditions],
            "safety_signal": "review_required" if cautions else "no_flag_in_limited_checks",
            "cues": cues,
            "scope": "Educational motion and color only. The pattern is not a patient-specific physiological prediction."}
    return response
