"""Observable integrity tests for the available educational adapter.

These protect against invented provenance, unsupported numeric action effects,
patient carryover, and step-dependent fluid bookkeeping. No clinical validity
is inferred from these checks.
"""
import copy
import json

import pytest

from simulation.adapter import ReferenceTraceEngineAdapter
from simulation.capabilities import CapabilityManifest
from simulation.coverage import CoverageGate
from simulation.feasibility_check import run_feasibility


@pytest.fixture
def engine():
    result = ReferenceTraceEngineAdapter()
    result.initialize({"conditions": [], "baseline_measurements": {}})
    return result


def fluid(dose=500, duration=0, ingredient="saline", **changes):
    return {"event_id": "fluid", "ingredient_id": ingredient, "dose": dose,
            "unit": "mL", "route": "intravenous", "duration": duration,
            "simulation_time": 0, **changes}


def test_numerical_provenance_is_illustrative(engine):
    snap = engine.snapshot()
    assert all(q["capability"] == "illustrative" for q in snap["quantities"].values())
    assert all("pulse" not in q["source"].lower() for q in snap["quantities"].values())
    assert snap["coverage_flags"]["execution_mode"] == "ILLUSTRATIVE"
    assert snap["coverage_flags"]["patient_prediction"] is False


def test_zero_dose_is_noop(engine):
    before = engine.snapshot()["quantities"]
    assert engine.apply_event(fluid(dose=0))
    engine.advance(60)
    assert engine.snapshot()["quantities"] == before


def test_bolus_uses_dose_without_inventing_organ_responses(engine):
    before = engine.snapshot()["quantities"]
    assert engine.apply_event(fluid())
    after = engine.snapshot()["quantities"]
    assert after["total_fluid_volume"]["value"] == pytest.approx(42.5)
    assert {k: v for k, v in after.items() if k != "total_fluid_volume"} == {
        k: v for k, v in before.items() if k != "total_fluid_volume"}
    engine.advance(60)
    assert engine.snapshot()["quantities"] == after


def test_infusion_uses_duration_and_stops(engine):
    engine.apply_event(fluid(dose=600, duration=60))
    engine.advance(30)
    assert engine.state["total_fluid_volume"] == pytest.approx(42.3)
    engine.advance(120)
    assert engine.state["total_fluid_volume"] == pytest.approx(42.6)


def test_fluid_unit_conversion_is_explicit(engine):
    engine.apply_event(fluid(dose=0.5, unit="L"))
    assert engine.state["total_fluid_volume"] == pytest.approx(42.5)


def test_typed_dehydration_removes_only_requested_volume(engine):
    engine.apply_event(fluid(dose=0.1, ingredient="Dehydration", unit="fraction",
                            route="environmental", duration=60))
    engine.advance(120)
    assert engine.state["total_fluid_volume"] == pytest.approx(37.8)
    assert engine.state["glomerular_filtration_rate"] == 115


def test_output_interval_split_does_not_change_state(engine):
    other = ReferenceTraceEngineAdapter()
    other.initialize({})
    for e in (engine, other):
        e.apply_event(fluid(dose=600, duration=60))
    engine.advance(120)
    for _ in range(120):
        other.advance(1)
    assert engine.state == other.state


@pytest.mark.parametrize("change", [
    {"unit": "banana"}, {"route": "oral"}, {"dose": float("inf")},
    {"dose": float("nan")}, {"duration": -1}, {"duration": float("inf")},
    {"simulation_time": 5},
])
def test_invalid_fluid_action_is_rejected_without_mutation(engine, change):
    before = engine.serialize()
    with pytest.raises(ValueError):
        engine.apply_event(fluid(**change))
    assert engine.serialize() == before


def test_excessive_dehydration_is_rejected_atomically(engine):
    before = copy.deepcopy(engine.state)
    with pytest.raises(ValueError):
        engine.apply_event(fluid(dose=50, ingredient="Dehydration", unit="L",
                                route="environmental"))
    assert engine.state == before


@pytest.mark.parametrize("delta", [float("inf"), float("nan"), -1])
def test_invalid_advance_is_rejected_without_mutation(engine, delta):
    before = engine.serialize()
    with pytest.raises(ValueError):
        engine.advance(delta)
    assert engine.serialize() == before


def test_ckd_diabetes_are_context_not_synthetic_measured_labs(engine):
    before = engine.snapshot()["quantities"]
    engine.initialize({"conditions": ["CKD"], "context": {"diabetes": True},
                       "baseline_measurements": {"egfr": {"value": None, "is_missing": True}}})
    assert engine.snapshot()["quantities"] == before
    assert engine.profile["baseline_measurements"]["egfr"]["value"] is None
    flags = engine.snapshot()["coverage_flags"]
    assert "CKD" in flags["context_only_conditions"]
    assert flags["patient_prediction"] is False


def test_patient_reinitialization_clears_all_prior_state(engine):
    engine.apply_event(fluid())
    engine.advance(20)
    engine.initialize({"conditions": []})
    assert engine.state["total_fluid_volume"] == 42
    assert engine.active_events == []
    assert engine.simulation_time == 0


def test_ignored_measured_baseline_is_explicit(engine):
    engine.initialize({"baseline_measurements": {
        "creatinine": {"value": 2.75, "unit": "mg/dL", "source": "lab"}}})
    flags = engine.snapshot()["coverage_flags"]
    assert "creatinine" in flags["ignored_baseline_inputs"]
    assert "model_baseline" in flags
    assert engine.profile["baseline_measurements"]["creatinine"]["value"] == 2.75


@pytest.mark.parametrize("ingredient, accepted", [
    ("ibuprofen", True), ("morphine", True), ("fentanyl", False), ("Opioid_Bolus", False),
])
def test_medication_never_changes_numerical_values(engine, ingredient, accepted):
    before = engine.snapshot()["quantities"]
    assert engine.apply_event(fluid(ingredient=ingredient, dose=5, unit="mg", route="oral")) is accepted
    engine.advance(60)
    assert engine.snapshot()["quantities"] == before
    if accepted:
        assert engine.active_events[-1]["capability_status"] == "evidence_only"
    else:
        assert engine.active_events == []


@pytest.mark.parametrize("ingredient", ["fake_ibuprofen", "saline_unvalidated_blend", "norepinephrine"])
def test_exact_ids_prevent_substring_capability_escape(engine, ingredient):
    before = engine.serialize()
    assert engine.apply_event(fluid(ingredient=ingredient)) is False
    assert engine.serialize() == before


def test_capability_and_mode_survive_strict_manifest_round_trip(engine):
    manifest = engine.capabilities()
    parsed = CapabilityManifest.model_validate(manifest)
    assert parsed.model_dump(mode="json") == manifest
    assert parsed.execution_mode == "ILLUSTRATIVE"
    assert CoverageGate().evaluate_intervention("norepinephrine")["numerical_effect"] is False
    assert CoverageGate.CONDITION_ALIASES["ckd"] == "CKD"


def test_advertised_numerical_metrics_match_actual_snapshot(engine):
    advertised = {key for key, value in engine.capabilities()["metrics"].items()
                  if value["capability"] in ("illustrative", "engine_simulated")}
    assert advertised == set(engine.snapshot()["quantities"])
    assert CoverageGate().evaluate_metric("hepatic_clearance_rate").value == "unsupported"


def test_condition_display_does_not_misidentify_renal_stenosis_as_ckd(engine):
    conditions = engine.capabilities()["conditions"]
    assert conditions["ChronicRenalStenosis"]["name"] == "Renal artery stenosis"
    assert conditions["CKD"]["engine_mapping"] is None


@pytest.mark.parametrize("start,duration", [(1e16, 1), (1e308, 1e308)])
def test_positive_duration_requires_finite_representable_completion(engine, start, duration):
    engine.advance(start)
    before = engine.serialize()
    with pytest.raises(ValueError):
        engine.apply_event(fluid(duration=duration, simulation_time=start))
    assert engine.serialize() == before


def test_positive_advance_cannot_silently_fail_to_move_clock(engine):
    engine.advance(1e16)
    before = engine.serialize()
    with pytest.raises(ValueError):
        engine.advance(1)
    assert engine.serialize() == before


def test_checkpoint_is_canonical_and_rejects_modified_or_incompatible_state(engine):
    engine.apply_event(fluid(dose=600, duration=60))
    engine.advance(30)
    checkpoint = engine.serialize()
    assert checkpoint == engine.serialize()
    restored = ReferenceTraceEngineAdapter()
    assert restored.restore(checkpoint)
    restored.advance(30)
    assert restored.state["total_fluid_volume"] == pytest.approx(42.6)
    for key, value in [("engine_version", "fake"), ("simulation_time", 999)]:
        altered = json.loads(checkpoint)
        altered["payload"][key] = value
        before = restored.serialize()
        with pytest.raises(ValueError):
            restored.restore(json.dumps(altered))
        assert restored.serialize() == before


def test_successful_illustrative_lifecycle_does_not_verify_real_physiology(capsys):
    result = run_feasibility()
    assert result["illustrative_lifecycle_passed"] is True
    assert result["physiology_engine_verified"] is False
    assert result["gate1_passed"] is False
