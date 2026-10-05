import hashlib
import json
import math

from backend.catalogue.registry import VERSION, conditions_by_id, drugs_by_id
from backend.database.writer import canonical_profile_hash
from backend.evidence.patient_registry import PatientEvidenceRegistry
from backend.schemas.domain import BaselineMeasurement, Intervention, PatientProfile, SimulationConfig
from backend.schemas.intake import PatientIntake

MEASUREMENTS = {
    "creatinine": ("Serum creatinine", "mg/dL", 0, 100),
    "egfr": ("eGFR", "mL/min/1.73m2", 0, 500),
    "alt": ("ALT", "U/L", 0, 100000), "ast": ("AST", "U/L", 0, 100000),
    "bilirubin": ("Total bilirubin", "mg/dL", 0, 100),
    "albumin": ("Albumin", "g/dL", 0, 20), "inr": ("INR", "ratio", 0, 100),
    "spo2": ("Oxygen saturation", "%", 0, 100),
    "respiratory_rate": ("Respiratory rate", "breaths/min", 0, 100),
    "heart_rate": ("Heart rate", "beats/min", 0, 300),
    "potassium": ("Potassium", "mmol/L", 0, 20),
    "glucose": ("Blood glucose", "mg/dL", 0, 3000),
}


def preflight(intake: PatientIntake):
    conditions, drugs = conditions_by_id(), drugs_by_id()
    reviewed_organs = {}
    for rule in PatientEvidenceRegistry().rules:
        if rule.review_status == "reviewed" and rule.ingredient_or_class in drugs:
            reviewed_organs.setdefault(rule.ingredient_or_class, set()).add(rule.target_organ)
    errors, warnings, gaps = [], [], []
    selected = []
    for organ, history in intake.organs.items():
        if history.status == "unknown":
            gaps.append(f"{organ.title()} history is unknown.")
        for index, condition in enumerate(history.conditions):
            info = conditions.get(condition.condition_id)
            field = f"organs.{organ}.conditions.{index}"
            if info is None:
                errors.append({"field": field, "message": "Select a condition from the catalogue."})
            elif info["organ"] != organ:
                errors.append({"field": field, "message": "Condition belongs to another system in this catalogue."})
            elif condition.severity not in info["severity_options"]:
                errors.append({"field": field + ".severity", "message": "Select a valid stage/severity or unknown."})
            elif condition.subtype not in info.get("subtypes", ["unknown"]):
                errors.append({"field": field + ".subtype", "message": "Select a valid subtype or unknown."})
            else:
                selected.append(info)
    cv = intake.organs["cardiovascular"]
    has_hypertension = any(item["canonical_id"] == "EssentialHypertension" for item in selected)
    if has_hypertension and intake.blood_pressure.status != "hypertension":
        errors.append({"field": "blood_pressure.status", "message": "Match BP history to the selected hypertension condition."})
    if intake.blood_pressure.status == "hypertension" and cv.status == "none_known":
        errors.append({"field": "organs.cardiovascular.status", "message": "Hypertension is a cardiovascular condition; record it in this system."})
    if intake.blood_pressure.status == "hypertension" and not has_hypertension:
        errors.append({"field": "organs.cardiovascular.conditions", "message": "Add hypertension to the cardiovascular conditions."})
    rows = []
    total_events = 0
    seen = set()
    for index, medication in enumerate(intake.medications):
        drug = drugs.get(medication.drug_id)
        prefix = f"medications.{index}"
        if not drug:
            errors.append({"field": prefix + ".drug_id", "message": "Select a medication from the catalogue."})
            continue
        if medication.unit not in drug["units"]:
            errors.append({"field": prefix + ".unit", "message": f"Use one of: {', '.join(drug['units'])}."})
        if medication.route not in drug["routes"]:
            errors.append({"field": prefix + ".route", "message": "Route is incompatible with the selected formulation."})
        if medication.duration_seconds and medication.route != "intravenous":
            errors.append({"field": prefix + ".duration_seconds", "message": "An infusion duration requires an intravenous route."})
        if medication.repeat_count > 1 and medication.interval_seconds <= 0:
            errors.append({"field": prefix + ".interval_seconds", "message": "Repeated administrations require a positive interval."})
        end = medication.time_seconds + (medication.repeat_count - 1) * medication.interval_seconds + medication.duration_seconds
        if end > intake.horizon_seconds:
            errors.append({"field": prefix + ".time_seconds", "message": "The last administration must finish within the assessment horizon."})
        if medication.repeat_count > 1 and medication.duration_seconds > medication.interval_seconds:
            warnings.append(f"{drug['name']}: repeated infusions overlap; confirm this schedule.")
        normalized = medication.model_dump_json()
        if normalized in seen:
            warnings.append(f"Duplicate {drug['name']} row; confirm both administrations are intentional.")
        seen.add(normalized)
        total_events += medication.repeat_count
        rows.append({"drug_id": drug["id"], "name": drug["name"], "coverage": "evidence_only" if drug["evidence_available"] else "unsupported",
                     "scope": drug["rule_scope"], "numerical_supported": False,
                     "associated_organs": drug["target_organs"],
                     "reviewed_rule_organs": sorted(reviewed_organs.get(drug["id"], set()))})
        if not drug["evidence_available"]:
            gaps.append(f"{drug['name']}: recorded administration only; no reviewed drug-specific assessment.")
    if total_events > 500:
        errors.append({"field": "medications", "message": "Schedule exceeds 500 administrations."})
    seen_measurements = set()
    for index, measurement in enumerate(intake.measurements):
        spec = MEASUREMENTS.get(measurement.name)
        if not spec or measurement.unit != spec[1] or not spec[2] <= measurement.value <= spec[3]:
            errors.append({"field": f"measurements.{index}", "message": "Measurement name, unit, or value is outside the supported input contract."})
        if measurement.name in seen_measurements:
            errors.append({"field": f"measurements.{index}", "message": "Enter one baseline per measurement."})
        seen_measurements.add(measurement.name)
    if len(intake.medications) > 1 or intake.patient.current_medications:
        gaps.append("The combined drug regimen and ongoing-medication interactions are not comprehensively assessed.")
    if intake.patient.allergies_status == "unknown":
        gaps.append("Allergy history is unknown.")
    if intake.patient.current_medications_status == "unknown":
        gaps.append("Ongoing medication history is unknown.")
    if intake.blood_pressure.systolic is None:
        gaps.append("No measured blood-pressure reading was supplied.")
    if any(item["canonical_id"] in ("CKD", "ChronicRenalStenosis") for item in selected):
        for key in ("egfr", "creatinine"):
            if key not in seen_measurements:
                gaps.append(f"No measured {MEASUREMENTS[key][0]} was supplied; quantitative renal assessment is unavailable.")
    return {"catalogue_version": VERSION, "can_run_evidence": not errors, "can_run_numerical": False,
            "patient_prediction": False, "errors": errors, "warnings": warnings,
            "missing_information": list(dict.fromkeys(gaps)), "medication_coverage": rows,
            "limitations": ["No verified patient-specific numerical physiology engine is active.",
                "Animation illustrates anatomy and administration; organ response and drug concentration are not predicted.",
                "Source-linked checks are limited and have not undergone independent clinical validation."],
            "schedule_count": total_events}


def prepare_intake(intake: PatientIntake, run_id: str):
    checks = preflight(intake)
    if checks["errors"]:
        raise ValueError("; ".join(f"{e['field']}: {e['message']}" for e in checks["errors"]))
    catalogue = conditions_by_id()
    ids = [catalogue[item.condition_id]["canonical_id"] for history in intake.organs.values() for item in history.conditions]
    context = {organ + "_history": history.status for organ, history in intake.organs.items()}
    context.update(blood_pressure_status=intake.blood_pressure.status, blood_pressure_control=intake.blood_pressure.control)
    for history in intake.organs.values():
        for item in history.conditions:
            if item.condition_id in ("cirrhosis", "decompensated_cirrhosis"):
                ids.append("HepaticCirrhosis")
                context["hepatic_impairment"] = {"Child-Pugh A": "mild", "Child-Pugh B": "moderate", "Child-Pugh C": "severe"}.get(item.severity, item.severity)
    measurements = {item.name: BaselineMeasurement(name=item.name, value=item.value, unit=item.unit, source=item.source)
                    for item in intake.measurements}
    if intake.blood_pressure.systolic is not None:
        for name, value in (("systolic", intake.blood_pressure.systolic), ("diastolic", intake.blood_pressure.diastolic)):
            measurements[name] = BaselineMeasurement(name=name, value=value, unit="mmHg", source="user_entered")
    profile = PatientProfile(patient_id="patient_" + run_id, age=intake.patient.age,
        sex=intake.patient.sex, mass_kg=intake.patient.mass_kg, display_name=intake.patient.name,
        gender=intake.patient.gender, intake=intake.model_dump(mode="json"),
        conditions=tuple(dict.fromkeys(ids)), context=context, baseline_measurements=measurements,
        current_medications=tuple(intake.patient.current_medications), allergies=tuple(intake.patient.allergies))
    config = SimulationConfig(run_id=run_id, profile_hash=canonical_profile_hash(profile),
        horizon_seconds=intake.horizon_seconds, sample_cadence_seconds=max(1, intake.horizon_seconds / 120),
        assumptions={"assessment_mode": "evidence_only", "catalogue_version": VERSION,
                     "patient_prediction": "false", "clinical_validation": "false"})
    interventions = []
    for row, medication in enumerate(intake.medications):
        for repeat in range(medication.repeat_count):
            event_id = f"{run_id}_med_{row}_{repeat}"
            factor = {"mg": 1, "g": 1000, "mcg": 0.001, "mL": 1, "L": 1000}[medication.unit]
            normalized_unit = "mL" if medication.unit in ("mL", "L") else "mg"
            interventions.append(Intervention(event_id=event_id, ingredient_id=medication.drug_id,
                dose=medication.dose * factor, unit=normalized_unit, route=medication.route,
                simulation_time=medication.time_seconds + repeat * medication.interval_seconds,
                duration=medication.duration_seconds, idempotency_key=event_id))
    return profile, config, interventions


def capture_assessment_basis(intake: PatientIntake, registry):
    conditions, drugs = conditions_by_id(), drugs_by_id()
    return {"version": "1.0.0", "scope": preflight(intake),
        "conditions": {c.condition_id: conditions[c.condition_id] for history in intake.organs.values() for c in history.conditions},
        "drugs": {m.drug_id: drugs[m.drug_id] for m in intake.medications},
        "measurements": {key: list(value) for key, value in MEASUREMENTS.items()},
        "rules": {rule.rule_id: rule.model_dump(mode="json") for rule in registry.rules},
        "sources": {source.source_id: source.model_dump(mode="json") for source in registry.sources}}
