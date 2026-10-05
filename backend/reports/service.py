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
from backend.reports.coverage import build_organ_coverage
from backend.reports.safety import build_safety_alerts
from backend.reports.pk import build_illustrative_pk

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

    series = []
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

    # No production parameter set has passed source and model review yet.
    # The ledger remains available; illustrative concentration is fail-closed.
    pk_series = build_illustrative_pk(administrations, drugs, horizon, last_time)

    report = {"schema_version": "1.0.0", "run_id": run_id, "cursor": cursor,
        "intake": intake.model_dump(mode="json"), "assessment_basis_pinned": bool(basis), "administrations": administrations,
        "status": status, "is_final": status == "completed", "clinical_validation": False, "patient_prediction": False,
        "created_at": datetime.fromtimestamp(run["created_at"], timezone.utc).isoformat(),
        "patient_id": profile["patient_id"], "patient": intake.patient.model_dump(),
        "blood_pressure": bp.model_dump(), "medications": medications, "schedule": run["initial_schedule"],
        "measurements": measurements, "organs": organs, "interactions": interactions, "snapshots": snapshots,
        "findings_timeline": findings_timeline, "administration_series": series, "pk_series": pk_series,
        "visual_responses": build_visual_responses(intake, conditions, drugs, administrations, findings_timeline),
        "organ_coverage": build_organ_coverage(drugs, rules, {}),
        "safety_alerts": build_safety_alerts(intake, administrations, drugs),
        "horizon_seconds": intake.horizon_seconds, "last_time": last_time,
        "scope": checks, "engine": {"name": run["config"]["engine_name"], "version": run["config"]["engine_version"]},
        "catalogue_version": checks["catalogue_version"], "limitations": checks["limitations"],
        "summary": {"concerns": sum(organ["outcome"] == "concern_identified" for organ in organs.values()),
                    "unassessed_systems": sum(organ["outcome"] == "unable_to_assess" for organ in organs.values()),
                    "medication_count": len(medications), "measurement_count": len(measurements)}}
    report["report_id"] = "PDTT-" + hashlib.sha256(canonical_json(report).encode()).hexdigest()[:12].upper()
    return writer.cache_assessment(report)
