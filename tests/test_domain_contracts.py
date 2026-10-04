"""Observer inputs must be immutable, finite, typed and JSON round-trippable."""
import json
import pytest
from pydantic import ValidationError
from backend.schemas.domain import (
    BaselineMeasurement, PatientProfile, SimulationConfig, Intervention,
    QuantitySnapshot, PhysiologySnapshot, RunEvent, AgentFinding, Checkpoint, ReviewRecord,
)
from backend.database.writer import PersistenceWriter, canonical_profile_hash
from simulation.worker import SimulationWorker


def profile(**changes):
    raw = dict(patient_id="p", age=45, sex="male", mass_kg=70)
    raw.update(changes)
    return PatientProfile(**raw)


def snapshot(**changes):
    raw = dict(run_id="r", sequence=1, simulation_time=0,
               quantities={"map": {"value": 90, "unit": "mmHg"}},
               coverage_flags={"limitations": ["illustrative"],
                               "assumptions": {"nested": [1, {"x": True}]}})
    raw.update(changes)
    return PhysiologySnapshot(**raw)


def action(**changes):
    raw = dict(event_id="i", ingredient_id="saline", dose=500, unit="mL",
               route="intravenous", simulation_time=0, idempotency_key="i")
    raw.update(changes)
    return Intervention(**raw)


@pytest.mark.parametrize("mutation", [
    lambda s: setattr(s, "sequence", 2),
    lambda s: setattr(s.quantities["map"], "value", 1),
    lambda s: s.quantities.__setitem__("map", {}),
    lambda s: s.coverage_flags["limitations"].append("changed"),
    lambda s: s.coverage_flags["assumptions"]["nested"][1].__setitem__("x", False),
])
def test_observer_snapshot_blocks_nested_mutation(mutation):
    s = snapshot()
    before = s.model_dump_json()
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        mutation(s)
    assert s.model_dump_json() == before


def test_profile_and_config_are_deeply_frozen():
    p = profile(conditions=["CKD"], context={"diabetes": True},
                baseline_measurements={"egfr": BaselineMeasurement(name="egfr", unit="mL/min")})
    c = SimulationConfig(run_id="r", profile_hash="h", assumptions={"mode": "example"})
    for mutation in [lambda: p.conditions.append("diabetes"),
                     lambda: p.context.__setitem__("diabetes", False),
                     lambda: setattr(p.baseline_measurements["egfr"], "value", 90),
                     lambda: c.assumptions.__setitem__("mode", "changed"),
                     lambda: setattr(action(), "dose", 0)]:
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            mutation()


def test_default_mappings_and_private_mapping_storage_cannot_be_mutated():
    for container in [profile().context, profile().baseline_measurements,
                      SimulationConfig(run_id="r", profile_hash="h").assumptions,
                      snapshot(coverage_flags={}).coverage_flags]:
        with pytest.raises((TypeError, AttributeError)):
            container.__setitem__("changed", 1)
    with pytest.raises((TypeError, AttributeError)):
        del snapshot().coverage_flags._data


@pytest.mark.parametrize("factory", [
    lambda: RunEvent(run_id="r", sequence=1, simulation_time=0, wall_clock_time=float("inf"), event_type="X"),
    lambda: AgentFinding(finding_id="f", run_id="r", sequence=True, simulation_time=0, organ="renal", category="x", severity="unknown", coverage="unsupported", message="x"),
    lambda: Checkpoint(checkpoint_id="c", run_id="r", sequence=1, simulation_time=float("inf"), serialized_engine_state="s", event_cursor=1, content_hash="h"),
    lambda: ReviewRecord(review_id="v", run_id="r", reviewer="test", timestamp=float("nan"), status="preliminary", notes="test"),
])
def test_remaining_public_records_reject_invalid_numbers(factory):
    with pytest.raises(ValidationError):
        factory()


@pytest.mark.parametrize("capability,source", [("evidence_only", "evidence"),
                                               ("illustrative", "unverified"),
                                               ("engine_simulated", "unverified")])
def test_quantitative_claim_needs_numerical_source(capability, source):
    with pytest.raises(ValidationError):
        QuantitySnapshot(value=90, unit="mmHg", capability=capability, source=source)


def test_detached_input_dump_and_json_round_trip():
    metadata = {"nested": [1, {"x": True}]}
    s = snapshot(coverage_flags=metadata)
    metadata["nested"][1]["x"] = False
    dumped = s.model_dump()
    dumped["coverage_flags"]["nested"][1]["x"] = False
    assert s.coverage_flags["nested"][1]["x"] is True
    assert PhysiologySnapshot.model_validate_json(s.model_dump_json()) == s
    assert s.model_copy(deep=True) == s
    assert json.loads(s.model_dump_json()) == s.model_dump(mode="json")
    assert PhysiologySnapshot.model_json_schema()["properties"]["quantities"]["type"] == "object"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "90", "banana"])
def test_invalid_quantity_value_cannot_escape_validation(bad):
    with pytest.raises(ValidationError):
        snapshot(quantities={"map": {"value": bad, "unit": "mmHg"}})


@pytest.mark.parametrize("factory", [
    lambda x: profile(mass_kg=x),
    lambda x: BaselineMeasurement(name="egfr", value=x, unit="mL/min"),
    lambda x: action(dose=x),
    lambda x: action(simulation_time=x),
    lambda x: action(duration=x),
    lambda x: SimulationConfig(run_id="r", profile_hash="h", horizon_seconds=x),
    lambda x: SimulationConfig(run_id="r", profile_hash="h", sample_cadence_seconds=x),
    lambda x: snapshot(simulation_time=x),
])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "10"])
def test_numeric_inputs_are_finite_and_not_coerced(factory, bad):
    with pytest.raises(ValidationError):
        factory(bad)


@pytest.mark.parametrize("bad", [{"x": float("nan")}, {"x": object()}, {"x": {1, 2}}, {1: "key"}])
def test_snapshot_metadata_requires_json_values(bad):
    with pytest.raises(ValidationError):
        snapshot(coverage_flags=bad)


def test_extra_fields_bad_capabilities_and_untyped_quantities_are_rejected():
    for changes in [{"quantities": {"map": {"value": 90, "unit": "mmHg", "typo": 1}}},
                    {"quantities": {"map": {"value": 90, "unit": "mmHg", "capability": "safe"}}},
                    {"unexpected": "silently dropped"}]:
        with pytest.raises(ValidationError):
            snapshot(**changes)


def test_copy_updates_are_revalidated():
    for original, update in [(snapshot(), {"simulation_time": float("nan")}),
                             (action(), {"dose": "500"}),
                             (profile(), {"age": True}),
                             (snapshot(), {"quantities": {"map": {"value": "bad", "unit": "mmHg"}}})]:
        with pytest.raises(ValidationError):
            original.model_copy(update=update)
    assert snapshot().model_copy(update={"sequence": 2}).sequence == 2


def test_deprecated_copy_revalidates_scalar_updates():
    with pytest.raises(ValidationError):
        snapshot().copy(update={"simulation_time": "bad"})


def test_deprecated_copy_keeps_nested_replacements_frozen():
    data = {"labels": ["original"]}
    copied = snapshot().copy(update={"coverage_flags": data})
    data["labels"].append("caller change")
    assert copied.coverage_flags["labels"] == ("original",)
    with pytest.raises((TypeError, AttributeError)):
        copied.coverage_flags["labels"].append("observer change")
    assert snapshot().copy(update={"sequence": 2}).sequence == 2


@pytest.mark.parametrize("factory", [
    lambda: profile(conditions=["x" * 4096 for _ in range(1000)]),
    lambda: profile(context={str(n): "x" * 4096 for n in range(8)}),
    lambda: SimulationConfig(run_id="r", profile_hash="h", assumptions={str(n): "x" * 4096 for n in range(8)}),
    lambda: action(event_id="x" * 4096),
    lambda: snapshot(coverage_flags={"message": "x" * 40000}),
    lambda: snapshot(coverage_flags={"values": list(range(2000))}),
])
def test_observer_payloads_have_local_size_and_width_budgets(factory):
    with pytest.raises(ValidationError):
        factory()


def test_baseline_missingness_and_key_identity():
    m = BaselineMeasurement(name="egfr", unit="mL/min")
    assert m.value is None and m.is_missing
    with pytest.raises(ValidationError):
        BaselineMeasurement(name="egfr", unit="mL/min", value=90, is_missing=True)
    with pytest.raises(ValidationError):
        profile(baseline_measurements={"creatinine": m})


@pytest.mark.parametrize("changes", [{"unit": "banana"}, {"route": "banana"},
                                     {"ingredient_id": "morphine", "unit": "mL"},
                                     {"unit": "mg"}, {"route": "oral"},
                                     {"ingredient_id": "Dehydration", "route": "environmental", "unit": "fraction", "dose": 2}])
def test_units_and_known_action_routes_are_checked(changes):
    with pytest.raises(ValidationError):
        action(**changes)


@pytest.mark.parametrize("changes", [{"horizon_seconds": 3601},
                                     {"sample_cadence_seconds": 0.0001},
                                     {"horizon_seconds": 0}])
def test_local_run_resource_bounds(changes):
    with pytest.raises(ValidationError):
        SimulationConfig(run_id="r", profile_hash="h", **changes)


@pytest.mark.parametrize("actions", [
    [dict(simulation_time=11)], [dict(simulation_time=9, duration=2)],
    [dict(event_id=str(n), idempotency_key=str(n)) for n in range(501)],
])
def test_invalid_schedule_rejected_before_creating_a_run(actions):
    w = PersistenceWriter(":memory:")
    try:
        with pytest.raises(ValueError):
            SimulationWorker("r", profile(), SimulationConfig(run_id="r", profile_hash="h", horizon_seconds=10),
                             [action(**x) for x in actions], w)
        assert w.get_run("r") is None
    finally:
        w.close()


def test_database_and_event_payload_round_trip_frozen_snapshot(tmp_path):
    w = PersistenceWriter(str(tmp_path / "contracts.db"))
    try:
        p = profile()
        w.create_run(SimulationConfig(run_id="r", profile_hash=canonical_profile_hash(p)), p)
        s = snapshot()
        w.commit_snapshot(s)
        restored = w.get_latest_snapshot("r")
        assert restored == s
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            restored.coverage_flags["assumptions"].__setitem__("new", 1)
        event = RunEvent(run_id="r", sequence=2, simulation_time=0, wall_clock_time=1,
                         event_type="SNAPSHOT", payload=s.model_dump())
        assert PhysiologySnapshot.model_validate(event.payload) == s
    finally:
        w.close()


def test_accepted_schedule_fits_event_payload_boundary():
    w = PersistenceWriter(":memory:")
    try:
        actions = [action(event_id=str(n), idempotency_key=str(n),
                          ingredient_id="ibuprofen", dose=0, unit="mg", route="oral")
                   for n in range(150)]
        p = profile(context={"description": "x" * 8192})
        owner = SimulationWorker("r", p, SimulationConfig(run_id="r", profile_hash="h", horizon_seconds=1), actions, w)
        owner.run()
        assert w.get_run("r")["status"] == "completed"
    finally:
        w.close()
