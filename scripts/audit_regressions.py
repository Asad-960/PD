"""Independent architecture audit probes. Application code is intentionally unchanged.

Run explicitly with pytest; this file is outside the existing tests/ collection.
Failures identify violated requirements, not fixes. See docs/audit-2026-10-04.md.
"""
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.database.writer import PersistenceWriter, canonical_profile_hash
from backend.evidence.registry import EvidenceRegistry
from backend.events.types import EventType, create_status_event, create_finding_event, create_snapshot_event
from backend.schemas.domain import (
    AgentFinding, BaselineMeasurement, Checkpoint, Intervention,
    PatientProfile, PhysiologySnapshot, SimulationConfig, DraftFinding,
)
from simulation.adapter import ReferenceTraceEngineAdapter
from simulation.capabilities import CapabilityLevel, CapabilityManifest
from simulation.coverage import CoverageGate
from simulation.worker import SimulationWorker

ROOT = Path(__file__).resolve().parents[1]


def profile(**changes):
    return PatientProfile(patient_id="audit_patient", age=55, sex="male", mass_kg=70,
                          **changes)


def config(run_id="audit_run", **changes):
    return SimulationConfig(run_id=run_id, profile_hash=canonical_profile_hash(profile()), horizon_seconds=10,
                            sample_cadence_seconds=10, **changes)


def intervention(ingredient="saline", event_id="audit_event", when=0, dose=500,
                 unit="mL", **changes):
    return Intervention(event_id=event_id, ingredient_id=ingredient, dose=dose,
                        unit=unit, route=changes.pop("route", "intravenous"), simulation_time=when,
                        idempotency_key=changes.pop("idempotency_key", event_id), **changes)


def snapshot(run_id="audit_run", sequence=10, **changes):
    return PhysiologySnapshot(run_id=run_id, sequence=sequence, simulation_time=10,
                              quantities={"mean_arterial_pressure": {"value": 90, "unit": "mmHg"}},
                              **changes)


def finding(run_id="audit_run", sequence=10, finding_id="audit_finding", **changes):
    defaults = dict(organ="renal", category="audit", severity="monitor",
                    coverage="evidence_only", message="Audit finding")
    defaults.update(changes)
    return AgentFinding(finding_id=finding_id, run_id=run_id, sequence=sequence,
                        simulation_time=10, **defaults)


@pytest.fixture
def writer():
    result = PersistenceWriter(":memory:")
    try:
        yield result
    finally:
        result.close()


def run_worker(writer, interventions, run_id="audit_run", engine=None):
    worker = SimulationWorker(run_id, profile(), config(run_id), interventions,
                              writer, engine_adapter=engine)
    worker.run()
    return worker


def test_A01_generated_formula_output_must_be_labeled_illustrative():
    engine = ReferenceTraceEngineAdapter()
    engine.initialize(profile().model_dump())
    result = engine.snapshot()["quantities"]["heart_rate"]
    assert result["capability"] == "illustrative", result
    assert result["source"] != "pulse_reference_engine"


def test_A02_measured_creatinine_is_used_or_ignored_input_is_disclosed():
    engine = ReferenceTraceEngineAdapter()
    p = profile(baseline_measurements={"creatinine": BaselineMeasurement(
        name="creatinine", value=2.75, unit="mg/dL", source="lab")})
    engine.initialize(p.model_dump())
    result = engine.snapshot()
    q = result["quantities"]["serum_creatinine"]
    assert q["value"] == 2.75 or result["coverage_flags"].get("ignored_baseline_inputs"), result


def test_A03_reinitialization_does_not_inherit_previous_patient():
    reused, fresh = ReferenceTraceEngineAdapter(), ReferenceTraceEngineAdapter()
    reused.initialize(profile(conditions=["CKD"]).model_dump())
    reused.initialize(profile().model_dump())
    fresh.initialize(profile().model_dump())
    assert reused.snapshot()["quantities"] == fresh.snapshot()["quantities"]


def test_A04_output_sampling_and_interval_splits_do_not_change_physiology():
    whole, split = ReferenceTraceEngineAdapter(), ReferenceTraceEngineAdapter()
    for engine in (whole, split):
        engine.initialize(profile().model_dump())
        engine.apply_event({"ingredient_id": "Dehydration", "dose": 600, "unit": "mL",
                            "route": "environmental", "duration": 120,
                            "simulation_time": 0, "event_id": "stress"})
    whole.advance(120)
    for _ in range(120):
        split.advance(1)
    assert whole.state["glomerular_filtration_rate"] == pytest.approx(
        split.state["glomerular_filtration_rate"], rel=1e-10)


def test_A05_zero_dose_saline_cannot_add_fluid():
    engine = ReferenceTraceEngineAdapter()
    engine.initialize(profile().model_dump())
    before = dict(engine.state)
    engine.apply_event(intervention(dose=0).model_dump())
    engine.advance(60)
    assert engine.state == before


def test_A06_coverage_matches_actual_adapter_support():
    gate, engine = CoverageGate(), ReferenceTraceEngineAdapter()
    engine.initialize(profile().model_dump())
    assert gate.evaluate_intervention("saline")["numerical_effect"]
    assert engine.apply_event(intervention("saline").model_dump())
    assert not gate.evaluate_intervention("norepinephrine")["numerical_effect"]
    assert not engine.apply_event(intervention("norepinephrine", dose=1, unit="mg").model_dump())


def test_A07_typed_dehydration_event_reaches_the_adapter(writer):
    engine = ReferenceTraceEngineAdapter()
    run_worker(writer, [intervention("Dehydration", unit="fraction", dose=0.1,
                                    route="environmental")], engine=engine)
    event = engine.active_events[0]
    assert event["capability_status"] != "unsupported", event


def test_A08_snapshot_validity_is_not_silently_dropped():
    engine = ReferenceTraceEngineAdapter()
    engine.initialize(profile().model_dump())
    raw = engine.snapshot()
    raw["is_valid"] = False
    raw["numerical_error_code"] = "INVALID_STATE"
    assert not PhysiologySnapshot.model_validate(raw).is_valid


def test_A09_council_snapshot_prevents_shared_nested_mutation():
    s = snapshot()
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        s.quantities["mean_arterial_pressure"].value = 1


def test_A10_malformed_quantity_cannot_escape_through_untyped_dict():
    with pytest.raises(ValidationError):
        PhysiologySnapshot(run_id="x", sequence=1, simulation_time=0,
                            quantities={"heart_rate": {"value": "banana", "unit": "bpm"}})


def test_A11_medication_unit_must_be_validated():
    with pytest.raises((ValidationError, ValueError)):
        intervention("morphine", unit="banana")


def test_A12_nonfinite_horizon_is_rejected():
    with pytest.raises(ValidationError):
        SimulationConfig(run_id="x", profile_hash="x", horizon_seconds=float("inf"))


def test_A13_manifest_metadata_survives_typed_validation():
    raw = json.loads((ROOT / "simulation/capability-manifest.json").read_text())
    parsed = CapabilityManifest.model_validate(raw).model_dump()
    assert parsed.get("execution_mode") == raw["execution_mode"]
    assert parsed.get("engine_version") == raw["engine_version"]


def test_A14_unreviewed_rules_do_not_enter_primary_findings():
    registry = EvidenceRegistry()
    for rule in registry.rules:
        rule.review_status = "unreviewed"
    findings = registry.evaluate_rules(profile(conditions=["CHF"]), snapshot(),
                                        [intervention("IV_Saline_Infusion")])
    assert findings == []


def test_A15_severe_hepatic_context_is_not_silently_less_covered_than_moderate():
    registry = EvidenceRegistry()
    drug = intervention("morphine", dose=5, unit="mg")
    moderate = registry.evaluate_rules(profile(context={"hepatic_impairment": "moderate"}),
                                        snapshot(), [drug])
    severe = registry.evaluate_rules(profile(context={"hepatic_impairment": "severe"}),
                                      snapshot(), [drug])
    assert moderate
    assert severe, "Severe hepatic impairment returned no finding or coverage warning."


def test_A16_missing_threshold_is_explicitly_unknown():
    registry = EvidenceRegistry()
    p = profile(baseline_measurements={"egfr": BaselineMeasurement(name="egfr", value=90, unit="mL/min")})
    empty = PhysiologySnapshot(run_id="audit_run", sequence=1, simulation_time=0, quantities={})
    findings = registry.evaluate_rules(p, empty, [intervention("ibuprofen", dose=800, unit="mg")])
    assert any(f.severity == "unknown" for f in findings), findings


def test_A17_event_id_is_not_a_drug_trigger():
    registry = EvidenceRegistry()
    p = profile(conditions=["CKD"], baseline_measurements={"egfr": BaselineMeasurement(
        name="egfr", value=60, unit="mL/min")})
    inv = intervention("unrelated_substance", event_id="ibuprofen")
    assert registry.evaluate_rules(p, snapshot(), [inv]) == []


def test_A18_finding_identity_is_scoped_to_run():
    registry = EvidenceRegistry()
    p = profile(conditions=["CHF"])
    inv = intervention("IV_Saline_Infusion")
    a = registry.evaluate_rules(p, snapshot("run_a"), [inv])
    b = registry.evaluate_rules(p, snapshot("run_b"), [inv])
    assert a[0].finding_id != b[0].finding_id


def test_A19_each_finding_gets_a_distinct_stream_sequence(writer):
    writer.create_run(config(), profile())
    registry = EvidenceRegistry()
    p = profile(conditions=["CKD", "CHF"], baseline_measurements={"egfr": BaselineMeasurement(
        name="egfr", value=60, unit="mL/min")})
    findings = registry.evaluate_rules(p, snapshot(), [intervention("ibuprofen", unit="mg"),
                                                       intervention("IV_Saline_Infusion", event_id="fluid")])
    assert len(findings) == 2
    source = snapshot(sequence=1)
    drafts = [DraftFinding(run_id=f.run_id, source_snapshot_sequence=source.sequence,
                           simulation_time=source.simulation_time, organ=f.organ,
                           category=f.category, severity=f.severity,
                           inputs_observed=f.inputs_observed, rule_id=f.rule_id,
                           evidence_ids=f.evidence_ids, coverage=f.coverage,
                           message=f.message, limitations=f.limitations)
              for f in findings]
    persisted = writer.commit_transition(snapshot=source,
                                         events=[create_snapshot_event(source)], drafts=drafts)
    assert len(persisted) == 2
    assert len({f.sequence for f in persisted}) == 2
    assert len(writer.get_events_after("audit_run")) == 3


def test_A20_schema_version_round_trips(writer):
    writer.create_run(config(), profile())
    e = create_status_event("audit_run", 1, 0, EventType.RUN_STARTED)
    e.schema_version = "2.0.0"
    writer.append_event(e)
    assert writer.get_events_after("audit_run")[0].schema_version == "2.0.0"


def test_A21_append_rejects_out_of_order_sequence(writer):
    writer.create_run(config(), profile())
    writer.append_event(create_status_event("audit_run", 1, 0, EventType.RUN_STARTED))
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.append_event(create_status_event("audit_run", 0, 0, EventType.RUN_PAUSED))


def test_A22_finding_id_collision_cannot_rewrite_another_run(writer):
    writer.create_run(config("run_a"), profile())
    writer.create_run(config("run_b"), profile())
    writer.save_finding(finding("run_a", finding_id="same"))
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.save_finding(finding("run_b", finding_id="same", message="Branch B"))


def test_A23_changed_run_configuration_cannot_rewrite_history(writer):
    writer.create_run(config(), profile())
    changed = config().model_copy(update={"profile_hash": "different"})
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.create_run(changed, profile())


def test_A24_snapshot_and_event_are_one_atomic_commit(writer, monkeypatch):
    # The bundle replaces the old two-call boundary: inject after the snapshot
    # insert but before the event insert within the same transaction.
    original_insert = writer._insert_event

    def fail_snapshot_event(event):
        if event.event_type == "SNAPSHOT_COMMITTED":
            raise RuntimeError("Injected failure inside snapshot transaction")
        return original_insert(event)

    monkeypatch.setattr(writer, "_insert_event", fail_snapshot_event)
    with pytest.raises(RuntimeError, match="Injected failure"):
        run_worker(writer, [])
    assert writer.get_latest_snapshot("audit_run") is None, "Orphan snapshot was already committed."


def test_A25_duplicate_idempotency_key_does_not_apply_twice(writer):
    engine = ReferenceTraceEngineAdapter()
    inv = intervention("saline", event_id="first", idempotency_key="same")
    retry = intervention("saline", event_id="retry", idempotency_key="same")
    run_worker(writer, [inv, retry], engine=engine)
    assert len(engine.active_events) == 1


def test_A26_same_intervention_id_in_fork_cannot_overwrite_parent(writer):
    writer.create_run(config("run_a"), profile())
    writer.create_run(config("run_b"), profile())
    writer.save_intervention("run_a", intervention(dose=500))
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.save_intervention("run_b", intervention(dose=1000))


def test_A27_worker_constructor_rejects_run_id_mismatch(writer):
    with pytest.raises((ValueError, ValidationError)):
        SimulationWorker("different_run", profile(), config(), [], writer)


def test_A28_engine_failure_return_is_not_logged_as_applied(writer):
    class RejectingEngine(ReferenceTraceEngineAdapter):
        def apply_event(self, event):
            return False

    with pytest.raises(RuntimeError, match="action"):
        run_worker(writer, [intervention()], engine=RejectingEngine())
    events = writer.get_events_after("audit_run")
    assert not any(e.event_type == "INTERVENTION_APPLIED" for e in events)


def test_A29_pause_resume_is_persisted(writer):
    worker = SimulationWorker("audit_run", profile(), config(), [], writer)
    worker.pause()
    thread = worker.start_in_background()
    try:
        worker.resume()
        thread.join(2)
        assert not thread.is_alive()
        types = [e.event_type for e in writer.get_events_after("audit_run")]
        assert "RUN_PAUSED" in types and "RUN_RESUMED" in types, types
    finally:
        worker.cancel()
        thread.join(2)


def test_A30_background_start_cannot_create_two_active_owners(writer):
    entered = threading.Event()
    release = threading.Event()

    class BlockingEngine(ReferenceTraceEngineAdapter):
        def initialize(self, p, assumptions=None):
            entered.set()
            assert release.wait(2)
            return super().initialize(p, assumptions)

    errors = []
    worker = SimulationWorker("audit_run", profile(), config(), [], writer,
                              engine_adapter=BlockingEngine())
    original = worker.run

    def capture():
        try:
            original()
        except Exception as error:
            errors.append(str(error))

    worker.run = capture
    a = worker.start_in_background()
    b = None
    try:
        assert entered.wait(2)
        try:
            b = worker.start_in_background()
        except (RuntimeError, ValueError):
            return
        assert b is a, "Second active worker thread was created."
    finally:
        release.set()
        worker.cancel()
        a.join(2)
        if b is not None and b is not a:
            b.join(2)


def test_A31_checkpoint_has_worker_schedule_for_restoration(writer):
    run_worker(writer, [intervention(when=5)])
    checkpoint = writer.get_checkpoint("pre_intervention_audit_event")
    engine_state = json.loads(checkpoint.serialized_engine_state)
    fields = checkpoint.model_dump()
    assert fields.get("pending_schedule") or engine_state.get("pending_schedule")
    assert fields.get("engine_version") or engine_state.get("engine_version")


def test_A32_future_intervention_is_not_active_early():
    registry = EvidenceRegistry()
    findings = registry.evaluate_rules(profile(conditions=["CHF"]), snapshot(),
                                        [intervention("IV_Saline_Infusion", when=100)])
    assert findings == []


def test_A33_canonical_condition_alias_matches_registry():
    registry = EvidenceRegistry()
    assert CoverageGate().evaluate_condition("chronic_heart_failure") != CapabilityLevel.UNSUPPORTED
    findings = registry.evaluate_rules(profile(conditions=["chronic_heart_failure"]), snapshot(),
                                        [intervention("IV_Saline_Infusion")])
    assert findings, "Coverage recognizes the condition but registry silently misses it."


def test_A34_evidence_warning_does_not_depend_on_unused_egfr_lab():
    registry = EvidenceRegistry()
    findings = registry.evaluate_rules(profile(conditions=["CKD"]), snapshot(),
                                        [intervention("ibuprofen", dose=800, unit="mg")])
    assert any(f.coverage == "evidence_only" and f.severity != "unknown" for f in findings)
    # Additional quantitative-personalization limits should remain separately visible.


def test_A35_failed_database_write_rolls_back_transaction(tmp_path):
    w = PersistenceWriter(str(tmp_path / "rollback.db"))
    try:
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            w.append_event(create_status_event("nonexistent_run", 1, 0, EventType.RUN_STARTED))
        assert not w._conn.in_transaction, "Failed write retained an open transaction."
    finally:
        w.close()


def test_A36_cancel_during_final_advance_is_not_reported_completed(writer):
    entered = threading.Event()
    release = threading.Event()
    errors = []

    class BlockingAdvance(ReferenceTraceEngineAdapter):
        def advance(self, delta):
            entered.set()
            assert release.wait(2)
            return super().advance(delta)

    worker = SimulationWorker("audit_run", profile(), config(), [], writer,
                              engine_adapter=BlockingAdvance())
    original = worker.run

    def capture():
        try:
            original()
        except Exception as error:
            errors.append(str(error))

    worker.run = capture
    thread = worker.start_in_background()
    try:
        assert entered.wait(2)
        worker.cancel()
        release.set()
        thread.join(2)
        assert not thread.is_alive()
        assert not errors, errors
        assert writer.get_run("audit_run")["status"] == "cancelled"
    finally:
        release.set()
        thread.join(2)


def test_A37_append_only_snapshot_cannot_be_replaced(writer):
    writer.create_run(config(), profile())
    original = snapshot()
    writer.commit_snapshot(original)
    # Construct a valid competing record; nested mutation is now disallowed.
    changed = original.model_copy(update={"quantities": {
        "mean_arterial_pressure": {"value": 1, "unit": "mmHg"}}})
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        writer.commit_snapshot(changed)


def test_CONTROL_cancel_wakes_paused_worker(writer):
    worker = SimulationWorker("audit_run", profile(), config(), [], writer)
    worker.pause()
    thread = worker.start_in_background()
    worker.cancel()
    thread.join(2)
    assert not thread.is_alive()
    assert writer.get_run("audit_run")["status"] == "cancelled"


def test_CONTROL_time_zero_equal_time_and_horizon_interventions_are_scheduled(writer):
    invs = [intervention("ibuprofen", event_id="zero", when=0, unit="mg"),
            intervention("ibuprofen", event_id="same_a", when=5, unit="mg"),
            intervention("ibuprofen", event_id="same_b", when=5, unit="mg"),
            intervention("ibuprofen", event_id="end", when=10, unit="mg")]
    run_worker(writer, invs)
    times = [e.simulation_time for e in writer.get_events_after("audit_run")
             if e.event_type == "INTERVENTION_APPLIED"]
    assert times == [0, 5, 5, 10]


def test_CONTROL_file_backed_query_plans_and_integrity(tmp_path):
    w = PersistenceWriter(str(tmp_path / "plans.db"))
    try:
        w.create_run(config(), profile())
        queries = [
            ("SELECT * FROM events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?", ("audit_run", 0, 100)),
            ("SELECT data FROM snapshots WHERE run_id=? ORDER BY sequence DESC LIMIT 1", ("audit_run",)),
            ("SELECT data FROM findings WHERE run_id=? ORDER BY sequence", ("audit_run",)),
        ]
        for sql, params in queries:
            plan = " ".join(str(tuple(r)) for r in w._conn.execute("EXPLAIN QUERY PLAN " + sql, params))
            assert "USING INDEX" in plan or "USING COVERING INDEX" in plan, plan
            assert "USE TEMP B-TREE" not in plan, plan
        assert w._conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert w._conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        w.close()
