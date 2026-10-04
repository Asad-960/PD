import pytest

from backend.schemas.domain import PatientProfile, PhysiologySnapshot, Intervention, BaselineMeasurement
from backend.evidence.registry import EvidenceRegistry
from backend.evidence.models import EvidenceRule, Precondition

@pytest.fixture
def registry():
    return EvidenceRegistry()

@pytest.fixture
def base_profile():
    return PatientProfile(
        patient_id="test_patient",
        age=45,
        sex="male",
        mass_kg=80.0,
        baseline_measurements={
            "egfr": BaselineMeasurement(name="egfr", value=90.0, unit="mL/min", is_missing=False)
        },
        conditions=[],
        context={},
        current_medications=[],
        allergies=[]
    )

@pytest.fixture
def base_snapshot():
    return PhysiologySnapshot(
        run_id="run_test",
        sequence=1,
        simulation_time=10.0,
        quantities={
            "mean_arterial_pressure": {"value": 90.0, "unit": "mmHg", "source": "test_engine", "capability": "engine_simulated"}
        }
    )

def test_positive_evidence_rule(registry, base_profile, base_snapshot):
    # CKD + NSAID
    base_profile = base_profile.model_copy(update={"conditions": ["CKD"]})
    inv = Intervention(
        event_id="evt_1",
        ingredient_id="ibuprofen",
        dose=800,
        unit="mg",
        route="oral",
        simulation_time=0.0,
        idempotency_key="key"
    )
    
    findings = registry.evaluate_rules(base_profile, base_snapshot, [inv])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "RULE_NSAID_RENAL_HEMODYNAMIC"
    assert finding.severity == "critical"
    assert finding.organ == "renal"
    assert finding.coverage == "evidence_only"
    assert "SRC_KDIGO_AKI" in finding.evidence_ids
    
    # Test threshold trigger: MAP < 70 without CKD
    base_profile = base_profile.model_copy(update={"conditions": []})
    base_snapshot = base_snapshot.model_copy(update={"quantities": {
            "mean_arterial_pressure": {"value": 65.0, "unit": "mmHg", "source": "test_engine", "capability": "engine_simulated"}}})
    findings2 = registry.evaluate_rules(base_profile, base_snapshot, [inv])
    assert len(findings2) == 1
    assert findings2[0].rule_id == "RULE_NSAID_RENAL_HEMODYNAMIC"

def test_negative_evidence_rule(registry, base_profile, base_snapshot):
    # Healthy patient, no vulnerable conditions, no thresholds breached
    inv = Intervention(
        event_id="evt_1",
        ingredient_id="ibuprofen",
        dose=800,
        unit="mg",
        route="oral",
        simulation_time=0.0,
        idempotency_key="key"
    )
    
    findings = registry.evaluate_rules(base_profile, base_snapshot, [inv])
    assert len(findings) == 0

def test_missing_egfr_does_not_hide_qualitative_warning(registry, base_profile, base_snapshot):
    # The rule does not numerically use eGFR. Missing eGFR limits
    # personalization, but must not suppress the qualitative warning.
    base_profile = base_profile.model_copy(update={"conditions": ["CKD"], "baseline_measurements": {}})
    
    inv = Intervention(
        event_id="evt_1",
        ingredient_id="ibuprofen",
        dose=800,
        unit="mg",
        route="oral",
        simulation_time=0.0,
        idempotency_key="key"
    )
    
    findings = registry.evaluate_rules(base_profile, base_snapshot, [inv])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "critical"
    assert finding.coverage == "evidence_only"
    assert "missing eGFR" in finding.limitations

def test_draft_rule_guardrail(registry, base_profile, base_snapshot):
    # Add a mock draft rule that would otherwise trigger
    draft_rule = EvidenceRule(
        rule_id="RULE_DRAFT_TEST",
        version="1.0.0",
        target_organ="hepatic",
        category="test",
        severity="monitor",
        ingredient_or_class="test_drug",
        mechanism="test",
        preconditions=Precondition(
            trigger_interventions=["test_drug"]
        ),
        source_id="SRC_TEST",
        source_section="test",
        review_status="draft",
        limitations="test",
        user_message="test"
    )
    registry.rules.append(draft_rule)
    
    inv = Intervention(
        event_id="evt_1",
        ingredient_id="test_drug",
        dose=100,
        unit="mg",
        route="oral",
        simulation_time=0.0,
        idempotency_key="key"
    )
    
    findings = registry.evaluate_rules(base_profile, base_snapshot, [inv])
    assert len(findings) == 0 # Draft rule should not fire
