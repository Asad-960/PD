"""Read-only calculation probes against production intake, adapter and report code.

Uses fictional fixtures and a report-writer stub; the separate full test suite
exercises persistence and worker integration. No application source is changed.
"""
import copy
import json
import math
from pathlib import Path

from backend.intake import prepare_intake, capture_assessment_basis
from backend.schemas.intake import PatientIntake
from backend.evidence.patient_registry import PatientEvidenceRegistry
from backend.reports.service import build_report
from simulation.assessment_adapter import AssessmentTimelineAdapter


def case(drug="ibuprofen", dose=400, route="oral", horizon=60, **med):
    return {
        "patient": {"name": "Fictional audit", "age": 39, "gender": "female", "mass_kg": 61,
                    "allergies_status": "none_known", "current_medications_status": "none_known"},
        "organs": {o: {"status": "none_known", "conditions": []} for o in
                   ("cardiovascular", "renal", "hepatic", "respiratory")},
        "blood_pressure": {"status": "unknown"}, "measurements": [],
        "medications": [{"drug_id": drug, "dose": dose, "unit": "mg", "route": route,
                         "time_seconds": 0, "duration_seconds": 0, "repeat_count": 1,
                         "interval_seconds": 0, **med}], "horizon_seconds": horizon,
    }


class FixtureWriter:
    def __init__(self, data):
        self.data = data

    def read_assessment(self, run_id, cursor=None):
        return copy.deepcopy(self.data)

    def cache_assessment(self, report):
        return report


def report(payload, cutoff=None):
    intake = PatientIntake.model_validate(payload)
    profile, config, actions = prepare_intake(intake, "audit")
    last = intake.horizon_seconds if cutoff is None else cutoff
    events = [{"event_type": "INTERVENTION_APPLIED", "simulation_time": a.simulation_time,
               "payload": a.model_dump()} for a in actions if a.simulation_time <= last]
    events.append({"event_type": "RUN_COMPLETED" if cutoff is None else "RUN_STARTED",
                   "simulation_time": last, "payload": {}})
    data = {"run": {"created_at": 0, "initial_schedule": [a.model_dump() for a in actions],
                    "config": {"engine_name": "audit_fixture", "engine_version": "1"}},
            "profile": profile.model_dump(), "cursor": len(events), "events": events,
            "assessment_basis": capture_assessment_basis(intake, PatientEvidenceRegistry())}
    return build_report(FixtureWriter(data), "audit")


checks = []


def record(name, status, **details):
    checks.append({"name": name, "status": status, **details})


equivalent = [report(case(dose=d, unit=u)) for d, u in [(400, "mg"), (.4, "g"), (400000, "mcg")]]
assert all(r["administration_series"][0]["points"][-1]["value"] == 400 for r in equivalent)
assert all(r["pk_series"][0]["points"] == equivalent[0]["pk_series"][0]["points"] for r in equivalent)
record("Input unit normalization", "PASS", equivalent="400 mg = 0.4 g = 400000 mcg")

r = report(case(repeat_count=3, interval_seconds=20))
assert [a["simulation_time"] for a in r["administrations"]] == [0, 20, 40]
assert r["administration_series"][0]["points"][-1]["value"] == 1200
record("Repeated administration ledger", "PASS", times=[0, 20, 40], total_mg=1200)

p = case("saline", 500, "intravenous", unit="mL", duration_seconds=60)
r = report(p, cutoff=30)
assert r["administration_series"][0]["points"][-1]["value"] == 250
record("Partial infusion ledger", "PASS", recorded_time_seconds=30, delivered_mL=250)

p = case("saline", 500, "intravenous", unit="mL", duration_seconds=40,
         repeat_count=2, interval_seconds=20)
r = report(p, cutoff=40)
assert r["administration_series"][0]["points"][-1]["value"] == 750
record("Overlapping infusion ledger", "PASS", recorded_time_seconds=40, delivered_mL=750)

pk = report(case("morphine", 20, "intravenous", horizon=10))["pk_series"][0]
expected_mcg_L = 20 / 250 * 1000
assert pk["unit"] == "mcg/L" and pk["points"][0]["concentration"] == .08
record("Morphine concentration output units", "FAIL", expected_mcg_per_L=expected_mcg_L,
       actual_labeled_mcg_per_L=pk["points"][0]["concentration"], error_factor=1000)

pk = report(case("fentanyl", 100, "intravenous", horizon=10, unit="mcg"))["pk_series"][0]
assert pk["c_max"] == 0 and pk["points"][0]["concentration"] == 0
record("Fentanyl nonzero concentration erased by rounding", "FAIL",
       expected_initial_mcg_per_L=100/300, actual_cmax=pk["c_max"], actual_first_point=0)

pk = report(case("morphine", 20, "intravenous", horizon=3600, time_seconds=30))["pk_series"][0]
assert not any(pt["time"] == 30 for pt in pk["points"])
assert pk["t_max"] == 61.0
record("Delayed IV bolus peak timing", "FAIL", expected_peak_time_seconds=30,
       actual_peak_time_seconds=pk["t_max"], peak_underestimate_percent=round((1-pk["c_max"]/.08)*100, 2))

pk = report(case("furosemide", 40, "intravenous", horizon=3600,
                 time_seconds=10, duration_seconds=1))["pk_series"][0]
expected_peak = (40/(.00045*15))*(1-math.exp(-.00045))
assert pk["t_max"] == 61.0
record("Short infusion peak timing", "FAIL", expected_peak_time_seconds=11,
       actual_peak_time_seconds=pk["t_max"], expected_model_peak_mg_per_L=expected_peak,
       actual_reported_peak_mg_per_L=pk["c_max"])

pk = report(case("ibuprofen", 400, "oral", horizon=300))["pk_series"][0]
analytic_tmax = math.log(.0035/.00035)/(.0035-.00035)
analytic_cmax = (400*.0035)/(10*(.0035-.00035))*(math.exp(-.00035*analytic_tmax)-math.exp(-.0035*analytic_tmax))
assert pk["t_max"] == 300
record("Oral peak truncated by report horizon", "FAIL_AS_GLOBAL_CMAX",
       true_peak_time_under_implemented_formula_seconds=analytic_tmax,
       true_peak_under_implemented_formula_mg_per_L=analytic_cmax,
       reported_peak_time_seconds=pk["t_max"], reported_peak_mg_per_L=pk["c_max"],
       note="Reported peak is only the maximum of sampled points inside the selected window.")

r = report(case("saline", 500, "intravenous", unit="mL", duration_seconds=60), cutoff=30)
assert r["last_time"] == 30 and r["pk_series"][0]["points"][-1]["time"] == 60
record("Partial report PK extends into unrecorded infusion delivery", "FAIL",
       last_recorded_time_seconds=30, pk_end_time_seconds=60,
       delivered_recorded_mL=r["administration_series"][0]["points"][-1]["value"])

pk = report(case("saline", 500, "intravenous", unit="mL"))["pk_series"][0]
assert pk["points"][0]["concentration"] == .1
record("Saline plasma-volume unit contract", "FAIL", input_mL=500,
       actual_labeled_plasma_volume_mL=pk["points"][0]["concentration"],
       note="The drug concentration formula divides the fluid amount by vd=5000; no dimensional conversion to a plasma-volume trajectory exists.")

light=case(); heavy=case(); heavy["patient"]["mass_kg"]=120
assert report(light)["pk_series"] == report(heavy)["pk_series"]
record("Patient mass effect on PK", "MODEL_LIMITATION", masses_kg=[61,120], curves="identical")

# Verify the separate administration adapter agrees with report arithmetic.
intake=PatientIntake.model_validate(case("saline", 500, "intravenous", unit="mL", duration_seconds=60))
profile, config, actions=prepare_intake(intake,"adapter-audit")
adapter=AssessmentTimelineAdapter(); adapter.initialize(profile.model_dump(),{})
adapter.apply_event(actions[0].model_dump()); adapter.advance(30)
assert adapter.snapshot()["quantities"]["administered_saline"]["value"] == 250
record("Adapter/report infusion arithmetic agreement", "PASS", delivered_mL=250)

result={"scope":"Production calculation functions with fictional fixtures; full integration suite is separate.",
        "checks":checks,"pass_count":sum(c["status"]=="PASS" for c in checks),
        "defect_count":sum(c["status"].startswith("FAIL") for c in checks)}
Path("artifacts/backend-calculation-audit-2026-10-05.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
