import math

from backend.catalogue.registry import drugs_by_id
from backend.reports.pk import build_illustrative_pk


def model(unit="mg/L", **changes):
    spec = {"model_id": "one_compartment_reference_test", "parameter_source": "fictional unit test",
            "ka": .0035, "ke": .00035, "vd_l": 10.0, "unit": unit,
            "routes": ["oral", "intravenous"]}
    spec.update(changes)
    return spec


def event(drug_id, dose, time=0, duration=0, route="intravenous", unit="mg"):
    return {"event_id": f"{drug_id}-{time}", "ingredient_id": drug_id,
            "dose": dose, "unit": unit, "route": route,
            "simulation_time": time, "duration": duration}


def series(administrations, params, horizon=3600, cursor=None):
    drugs = drugs_by_id()
    return build_illustrative_pk(administrations, drugs, horizon, horizon if cursor is None else cursor,
                                 params)


def test_model_is_absent_without_documented_parameters():
    assert series([event("morphine", 20)], {}) == []


def test_morphine_mg_per_l_is_converted_to_mcg_per_l():
    row = series([event("morphine", 20)], {"morphine": model(unit="mcg/L", vd_l=250)})[0]
    assert row["unit"] == "mcg/L"
    assert row["points"][0]["concentration"] == 80
    assert row["c_max"] == 80
    assert row["peak_kind"] == "within_window"


def test_small_dose_remains_nonzero():
    row = series([event("fentanyl", .1)], {"fentanyl": model(unit="mcg/L", vd_l=300)})[0]
    assert math.isclose(row["points"][0]["concentration"], 1 / 3)


def test_bolus_and_short_infusion_peak_at_actual_event_boundary():
    bolus = series([event("morphine", 20, time=30)],
                   {"morphine": model(vd_l=250)})[0]
    assert bolus["t_max"] == 30
    assert [p["time"] for p in bolus["points"]].count(30) == 2
    infusion = series([event("furosemide", 40, time=10, duration=1)],
                      {"furosemide": model(ke=.00045, vd_l=15)})[0]
    assert infusion["t_max"] == 11
    assert math.isclose(infusion["c_max"],
                        (40 / (.00045 * 15)) * (1 - math.exp(-.00045)), rel_tol=1e-9)


def test_peak_is_qualified_as_window_maximum_and_partial_stops_at_cursor():
    oral = series([event("ibuprofen", 400, route="oral")],
                  {"ibuprofen": model()}, horizon=300)[0]
    assert oral["t_max"] == 300
    assert oral["peak_kind"] == "within_window"
    partial = series([event("morphine", 20)],
                     {"morphine": model()}, horizon=60, cursor=30)[0]
    assert partial["window_end"] == 30
    assert max(p["time"] for p in partial["points"]) == 30


def test_saline_never_uses_drug_concentration_formula():
    row = series([event("saline", 500, unit="mL")],
                 {"saline": model(unit="mL (plasma volume)")})
    assert row == []
