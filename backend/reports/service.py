import hashlib
import itertools
import math
from datetime import datetime, timezone

from backend.catalogue.registry import conditions_by_id, drugs_by_id
from backend.database.writer import canonical_json
from backend.evidence.patient_registry import PatientEvidenceRegistry
from backend.intake import MEASUREMENTS, preflight
from backend.schemas.intake import PatientIntake
from backend.reports.visual_response import build_visual_responses

LABELS = {"cardiovascular": "Heart & circulation", "renal": "Kidneys", "hepatic": "Liver", "respiratory": "Lungs & breathing"}


def build_report(writer, run_id, cursor=None):
    data = writer.read_assessment(run_id, cursor)
    if "cached" in data:
        return data["cached"]
    run, profile, cursor = data["run"], data["profile"], data["cursor"]
    if not profile.get("intake"):
        raise ValueError("This legacy preset has no complete patient intake. Create a new patient assessment for report export.")
    intake = PatientIntake.model_validate(profile["intake"])
    basis = data.get("assessment_basis")
    if basis:
        conditions, drugs = basis["conditions"], basis["drugs"]
        sources, rules = basis["sources"], basis["rules"]
        checks, measurement_specs = basis["scope"], basis["measurements"]
    else:
        # Pre-rebuild cases did not persist this context; never imply it was pinned.
        conditions, drugs = conditions_by_id(), drugs_by_id()
        registry = PatientEvidenceRegistry()
        sources = {source.source_id: source.model_dump() for source in registry.sources}
        rules = {rule.rule_id: rule.model_dump() for rule in registry.rules}
        checks, measurement_specs = preflight(intake), MEASUREMENTS
        checks["limitations"].append("Legacy assessment metadata was not pinned at submission; explanations use the current catalogue.")
    findings = {}
    findings_timeline = []
    administrations = []
    snapshots = []
    status = "queued"
    status_names = {"RUN_INITIALIZING": "initializing", "RUN_STARTED": "running", "RUN_PAUSED": "paused",
                    "RUN_RESUMED": "running", "RUN_COMPLETED": "completed", "RUN_FAILED": "failed", "RUN_CANCELLED": "cancelled"}
    for event in data["events"]:
        status = status_names.get(event["event_type"], status)
        if event["event_type"] == "FINDING_CREATED":
            finding = event["payload"]
            rule = rules.get(finding.get("rule_id"))
            finding = {**finding, "explanation": rule["mechanism"] if rule else finding.get("limitations", ""),
                       "sources": [sources[key] for key in finding.get("evidence_ids", []) if key in sources]}
            findings[(finding["organ"], finding.get("rule_id") or finding["category"])] = finding
            findings_timeline.append(finding)
        if event["event_type"] == "INTERVENTION_APPLIED":
            administrations.append(event["payload"])
        if event["event_type"] == "SNAPSHOT_COMMITTED":
            snapshot = event["payload"]
            snapshots.append({"sequence": snapshot["sequence"], "time": snapshot["simulation_time"],
                "quantities": [{"name": key, **quantity} for key, quantity in snapshot["quantities"].items()
                               if key.startswith("administered_")], "is_valid": snapshot["is_valid"]})
    organs = {}
    for organ, label in LABELS.items():
        history = intake.organs[organ]
        items = [finding for (system, _), finding in findings.items() if system == organ]
        concerns = [f for f in items if f["coverage"] == "evidence_only" and f["severity"] in ("monitor", "critical")]
        organs[organ] = {"label": label, "history_status": history.status,
            "conditions": [{**item.model_dump(), "name": conditions[item.condition_id]["name"],
                            "references": conditions[item.condition_id]["references"]} for item in history.conditions],
            "outcome": "concern_identified" if concerns else "unable_to_assess",
            "summary": "Source-linked medication concern identified." if concerns else "Patient-specific organ response is not modeled; normal function cannot be concluded.",
            "findings": items}
    medications = [{**item.model_dump(), "name": drugs[item.drug_id]["name"],
                    "drug_class": drugs[item.drug_id]["class"], "row_index": index,
                    "coverage": "evidence_only" if drugs[item.drug_id]["evidence_available"] else "unsupported"}
                   for index, item in enumerate(intake.medications)]
    measurements = [{**item.model_dump(), "label": measurement_specs[item.name][0], "provenance": "Entered measurement"} for item in intake.measurements]
    bp = intake.blood_pressure
    if bp.systolic is not None:
        measurements.extend([{"name": "systolic", "label": "Systolic blood pressure", "value": bp.systolic,
            "unit": "mmHg", "observed_at": bp.observed_at, "source": "user_entered", "provenance": "Entered measurement"},
            {"name": "diastolic", "label": "Diastolic blood pressure", "value": bp.diastolic, "unit": "mmHg",
            "observed_at": bp.observed_at, "source": "user_entered", "provenance": "Entered measurement"}])
    interactions = [{"drug_a": a["name"], "drug_b": b["name"], "outcome": "unable_to_assess",
                     "explanation": "No verified pair-specific interaction assessment is implemented; individual checks do not establish combination safety."}
                    for a, b in itertools.combinations(medications, 2) if a["drug_id"] != b["drug_id"]]
    last_time = max((event["simulation_time"] for event in data["events"]), default=0)
    horizon = max(intake.horizon_seconds, last_time, 10.0)

    # Pharmacokinetic profiles for simulated plasma concentration curves
    PK_DEFAULTS = {
        "ibuprofen": {"ka": 0.0035, "ke": 0.00035, "vd": 10.0, "t_half_s": 1980, "unit": "mg/L", "therapeutic_min": 15.0, "therapeutic_max": 50.0},
        "morphine": {"ka": 0.0060, "ke": 0.00030, "vd": 250.0, "t_half_s": 2310, "unit": "mcg/L", "therapeutic_min": 20.0, "therapeutic_max": 80.0},
        "acetaminophen": {"ka": 0.0045, "ke": 0.00028, "vd": 65.0, "t_half_s": 2475, "unit": "mg/L", "therapeutic_min": 10.0, "therapeutic_max": 25.0},
        "naproxen": {"ka": 0.0025, "ke": 0.00010, "vd": 12.0, "t_half_s": 6930, "unit": "mg/L", "therapeutic_min": 30.0, "therapeutic_max": 90.0},
        "lisinopril": {"ka": 0.0018, "ke": 0.00015, "vd": 120.0, "t_half_s": 4620, "unit": "mcg/L", "therapeutic_min": 10.0, "therapeutic_max": 40.0},
        "losartan": {"ka": 0.0030, "ke": 0.00035, "vd": 34.0, "t_half_s": 1980, "unit": "mcg/L", "therapeutic_min": 50.0, "therapeutic_max": 250.0},
        "furosemide": {"ka": 0.0045, "ke": 0.00045, "vd": 15.0, "t_half_s": 1540, "unit": "mg/L", "therapeutic_min": 1.0, "therapeutic_max": 5.0},
        "fentanyl": {"ka": 0.0090, "ke": 0.00055, "vd": 300.0, "t_half_s": 1260, "unit": "mcg/L", "therapeutic_min": 1.0, "therapeutic_max": 4.0},
        "naloxone": {"ka": 0.0150, "ke": 0.00085, "vd": 180.0, "t_half_s": 815, "unit": "mcg/L", "therapeutic_min": 5.0, "therapeutic_max": 25.0},
        "metformin": {"ka": 0.0022, "ke": 0.00025, "vd": 60.0, "t_half_s": 2770, "unit": "mg/L", "therapeutic_min": 1.0, "therapeutic_max": 4.0},
        "amlodipine": {"ka": 0.0012, "ke": 0.00005, "vd": 1400.0, "t_half_s": 13860, "unit": "mcg/L", "therapeutic_min": 3.0, "therapeutic_max": 15.0},
        "saline": {"ka": 0.0120, "ke": 0.00040, "vd": 5000.0, "t_half_s": 1730, "unit": "mL (plasma volume)", "therapeutic_min": 250.0, "therapeutic_max": 1000.0},
    }

    series = []
    pk_series = []
    for identifier in dict.fromkeys(m["drug_id"] for m in medications):
        events = [event for event in administrations if event["ingredient_id"] == identifier]
        knots = sorted({0.0, last_time, *(s["time"] for s in snapshots),
                        *(event["simulation_time"] for event in events),
                        *(min(last_time, event["simulation_time"] + event["duration"]) for event in events)})
        points = []
        for t in knots:
            # A pre-bolus point keeps the vertical dose jump at its actual time.
            boluses = [event for event in events if event["duration"] == 0 and event["simulation_time"] == t]
            def amount(include_bolus):
                amounts = []
                for event in events:
                    if t < event["simulation_time"]:
                        continue
                    if event in boluses and not include_bolus:
                        continue
                    fraction = min(1, max(0, (t-event["simulation_time"]) / event["duration"])) if event["duration"] else 1
                    amounts.append(event["dose"] * fraction)
                return math.fsum(amounts)
            if boluses:
                points.append({"time": t, "value": amount(False)})
            points.append({"time": t, "value": amount(True)})
        series.append({"drug_id": identifier, "name": drugs[identifier]["name"],
                       "unit": "mL" if identifier == "saline" else "mg", "points": points,
                       "provenance": "Arithmetic from recorded administrations; not pharmacokinetics"})

        # Calculate Pharmacokinetic (PK) Curve
        pk_info = PK_DEFAULTS.get(identifier, {"ka": 0.003, "ke": 0.0003, "vd": 50.0, "t_half_s": 2310, "unit": "mg/L", "therapeutic_min": 5.0, "therapeutic_max": 25.0})
        ka, ke, vd = pk_info["ka"], pk_info["ke"], pk_info["vd"]
        sample_count = 60
        time_step = horizon / max(sample_count - 1, 1)
        pk_points = []
        c_max = 0.0
        t_max = 0.0

        for step_i in range(sample_count):
            t_curr = min(horizon, step_i * time_step)
            conc_sum = 0.0
            for ev in events:
                t_ev = ev["simulation_time"]
                if t_curr < t_ev:
                    continue
                dose = ev["dose"]
                dur = ev.get("duration", 0)
                is_iv = ev.get("route") in ("intravenous", "injection")
                delta_t = t_curr - t_ev

                if dur > 0 and is_iv:
                    # IV Infusion
                    r_rate = dose / dur
                    if delta_t <= dur:
                        c_ev = (r_rate / (ke * vd)) * (1.0 - math.exp(-ke * delta_t))
                    else:
                        c_peak = (r_rate / (ke * vd)) * (1.0 - math.exp(-ke * dur))
                        c_ev = c_peak * math.exp(-ke * (delta_t - dur))
                elif is_iv and dur == 0:
                    # IV Bolus
                    c_ev = (dose / vd) * math.exp(-ke * delta_t)
                else:
                    # Extravascular / Oral 1-compartment Bateman
                    if abs(ka - ke) < 1e-6:
                        ka_adj = ke * 1.01
                    else:
                        ka_adj = ka
                    factor = (dose * ka_adj) / (vd * (ka_adj - ke))
                    c_ev = max(0.0, factor * (math.exp(-ke * delta_t) - math.exp(-ka_adj * delta_t)))
                conc_sum += c_ev

            if conc_sum > c_max:
                c_max = conc_sum
                t_max = t_curr
            pk_points.append({"time": round(t_curr, 1), "value": round(conc_sum, 3), "concentration": round(conc_sum, 3)})

        pk_series.append({
            "drug_id": identifier,
            "name": drugs[identifier]["name"],
            "unit": pk_info["unit"],
            "c_max": round(c_max, 2),
            "t_max": round(t_max, 1),
            "t_half_seconds": pk_info["t_half_s"],
            "therapeutic_min": pk_info["therapeutic_min"],
            "therapeutic_max": pk_info["therapeutic_max"],
            "points": pk_points,
            "provenance": "Simulated one-compartment pharmacokinetic plasma concentration curve",
        })

    report = {"schema_version": "1.0.0", "run_id": run_id, "cursor": cursor,
        "intake": intake.model_dump(mode="json"), "assessment_basis_pinned": bool(basis), "administrations": administrations,
        "status": status, "is_final": status == "completed", "clinical_validation": False, "patient_prediction": False,
        "created_at": datetime.fromtimestamp(run["created_at"], timezone.utc).isoformat(),
        "patient_id": profile["patient_id"], "patient": intake.patient.model_dump(),
        "blood_pressure": bp.model_dump(), "medications": medications, "schedule": run["initial_schedule"],
        "measurements": measurements, "organs": organs, "interactions": interactions, "snapshots": snapshots,
        "findings_timeline": findings_timeline, "administration_series": series, "pk_series": pk_series,
        "visual_responses": build_visual_responses(intake, conditions, drugs, administrations, findings_timeline),
        "horizon_seconds": intake.horizon_seconds, "last_time": last_time,
        "scope": checks, "engine": {"name": run["config"]["engine_name"], "version": run["config"]["engine_version"]},
        "catalogue_version": checks["catalogue_version"], "limitations": checks["limitations"],
        "summary": {"concerns": sum(organ["outcome"] == "concern_identified" for organ in organs.values()),
                    "unassessed_systems": sum(organ["outcome"] == "unable_to_assess" for organ in organs.values()),
                    "medication_count": len(medications), "measurement_count": len(measurements)}}
    report["report_id"] = "PDTT-" + hashlib.sha256(canonical_json(report).encode()).hexdigest()[:12].upper()
    return writer.cache_assessment(report)
