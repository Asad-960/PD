"""
Tests for Gate 2 (CoverageGate) and Gate 3 (Domain Data Contracts).
Verifies:
- CoverageGate capability evaluations (metrics, conditions, interventions)
- Scenario pre-flight audit and missing measurement detection
- Pydantic V2 domain models validation, serialization, and JSON schema generation
- Strict adherence to Rule 5 (No Silent Assumptions)
"""

import pytest
from pydantic import ValidationError

from simulation.capabilities import CapabilityLevel
from simulation.coverage import CoverageGate, ScenarioCoverageReport
from backend.schemas.domain import (
    BaselineMeasurement,
    PatientProfile,
    Intervention,
    SimulationConfig,
    PhysiologySnapshot,
    QuantitySnapshot,
    AgentFinding,
    RunEvent,
    Checkpoint,
    ReviewRecord,
)


@pytest.fixture
def coverage_gate():
    return CoverageGate()


# ============================================================================
# Gate 2: CoverageGate Tests
# ============================================================================

def test_coverage_gate_metric_evaluation(coverage_gate):
    """Verify metrics are accurately categorized per capability manifest."""
    assert coverage_gate.evaluate_metric("mean_arterial_pressure") == CapabilityLevel.ILLUSTRATIVE
    assert coverage_gate.evaluate_metric("heart_rate") == CapabilityLevel.ILLUSTRATIVE
    assert coverage_gate.evaluate_metric("glomerular_filtration_rate") == CapabilityLevel.ILLUSTRATIVE
    assert coverage_gate.evaluate_metric("alt_ast_levels") == CapabilityLevel.UNSUPPORTED
    assert coverage_gate.evaluate_metric("blood_glucose") == CapabilityLevel.UNSUPPORTED
    assert coverage_gate.evaluate_metric("unknown_synthetic_metric") == CapabilityLevel.UNSUPPORTED


def test_coverage_gate_condition_evaluation(coverage_gate):
    """Verify conditions and clinical aliases are categorized correctly."""
    assert coverage_gate.evaluate_condition("ChronicRenalStenosis") == CapabilityLevel.UNSUPPORTED
    assert coverage_gate.evaluate_condition("CKD") == CapabilityLevel.EVIDENCE_ONLY
    assert coverage_gate.evaluate_condition("EssentialHypertension") == CapabilityLevel.UNSUPPORTED
    assert coverage_gate.evaluate_condition("Type2DiabetesMellitus") == CapabilityLevel.UNSUPPORTED
    assert coverage_gate.evaluate_condition("diabetes") == CapabilityLevel.UNSUPPORTED
    assert coverage_gate.evaluate_condition("HepaticCirrhosis") == CapabilityLevel.EVIDENCE_ONLY
    assert coverage_gate.evaluate_condition("hypothetical_genetic_disorder") == CapabilityLevel.UNSUPPORTED


def test_coverage_gate_intervention_evaluation(coverage_gate):
    """Verify intervention classification and numerical effect gating."""
    # Dehydration: illustrative fluid bookkeeping only.
    dehydration_eval = coverage_gate.evaluate_intervention("Dehydration")
    assert dehydration_eval["capability"] == CapabilityLevel.ILLUSTRATIVE
    assert dehydration_eval["numerical_effect"] is True

    # High_Dose_NSAID: EVIDENCE_ONLY, numerical=False
    nsaid_eval = coverage_gate.evaluate_intervention("High_Dose_NSAID")
    assert nsaid_eval["capability"] == CapabilityLevel.EVIDENCE_ONLY
    assert nsaid_eval["numerical_effect"] is False
    assert nsaid_eval["evidence_effect"] is True

    # Ibuprofen alias
    ibuprofen_eval = coverage_gate.evaluate_intervention("ibuprofen")
    assert ibuprofen_eval["capability"] == CapabilityLevel.EVIDENCE_ONLY
    assert ibuprofen_eval["numerical_effect"] is False

    # Generic opioids cannot inherit a verified numerical or morphine-specific model.
    opioid_eval = coverage_gate.evaluate_intervention("Opioid_Bolus")
    assert opioid_eval["capability"] == CapabilityLevel.UNSUPPORTED
    assert opioid_eval["numerical_effect"] is False
    assert coverage_gate.evaluate_intervention("morphine")["capability"] == CapabilityLevel.EVIDENCE_ONLY
    assert coverage_gate.evaluate_intervention("morphine")["numerical_effect"] is False

    # Unknown drug
    unknown_eval = coverage_gate.evaluate_intervention("untested_experimental_drug")
    assert unknown_eval["capability"] == CapabilityLevel.UNSUPPORTED
    assert unknown_eval["numerical_effect"] is False


def test_coverage_gate_validate_scenario_missing_measurements(coverage_gate):
    """Verify validate_scenario detects missing required measurements for renal context."""
    profile = {
        "patient_id": "pt_001",
        "age": 60,
        "sex": "male",
        "mass_kg": 72.0,
        "conditions": ["CKD"],
        "context": {"diabetes": True},
        "baseline_measurements": {
            # eGFR is deliberately missing
            "egfr": {"name": "egfr", "value": None, "unit": "mL/min", "is_missing": True}
        }
    }
    interventions = [
        {"name": "Dehydration"},
        {"name": "High_Dose_NSAID"}
    ]

    report = coverage_gate.validate_scenario(profile, interventions)
    assert isinstance(report, ScenarioCoverageReport)
    assert report.overall_status == "illustrative_with_evidence"
    assert report.execution_mode == "ILLUSTRATIVE"
    assert report.physiology_engine_verified is False
    assert any("eGFR" in m for m in report.missing_measurements)
    assert any("NSAID" in a for a in report.evidence_only_aspects)
    assert any("Dehydration" in a for a in report.illustrative_aspects)
    assert report.simulated_aspects == []


# ============================================================================
# Gate 3: Domain Data Contracts Tests
# ============================================================================

def test_baseline_measurement_rule5_missingness():
    """Rule 5: Missing measurements must have is_missing=True and value=None."""
    # Valid missing measurement
    missing_lab = BaselineMeasurement(
        name="egfr",
        value=None,
        unit="mL/min",
        is_missing=True
    )
    assert missing_lab.is_missing is True
    assert missing_lab.value is None

    # Value is None, is_missing should automatically be set to True
    auto_missing = BaselineMeasurement(
        name="egfr",
        value=None,
        unit="mL/min"
    )
    assert auto_missing.is_missing is True

    # Valid provided measurement
    provided_lab = BaselineMeasurement(
        name="creatinine",
        value=1.1,
        unit="mg/dL",
        is_missing=False
    )
    assert provided_lab.is_missing is False
    assert provided_lab.value == 1.1

    # Conflict: non-None value with is_missing=True must be rejected
    with pytest.raises(ValidationError):
        BaselineMeasurement(
            name="serum_sodium",
            value=140.0,
            unit="mEq/L",
            is_missing=True
        )


def test_patient_profile_validation():
    """Verify PatientProfile enforces constraints (age, sex, mass)."""
    valid_profile = PatientProfile(
        patient_id="patient_123",
        age=52,
        sex="female",
        mass_kg=65.5,
        conditions=["EssentialHypertension"],
        context={"diabetes": True}
    )
    assert valid_profile.patient_id == "patient_123"
    assert valid_profile.sex == "female"

    # Invalid sex option
    with pytest.raises(ValidationError):
        PatientProfile(
            patient_id="patient_err",
            age=52,
            sex="other",  # must be male or female for engine
            mass_kg=65.5
        )

    # Invalid negative age
    with pytest.raises(ValidationError):
        PatientProfile(
            patient_id="patient_err",
            age=-5,
            sex="male",
            mass_kg=70.0
        )


def test_intervention_contract():
    """Verify Intervention model validation and unit/dose checks."""
    valid_intervention = Intervention(
        event_id="evt_101",
        ingredient_id="saline_0.9",
        dose=500.0,
        unit="mL",
        route="intravenous",
        simulation_time=120.0,
        duration=60.0,
        idempotency_key="idem_saline_101"
    )
    assert valid_intervention.dose == 500.0

    # Negative dose rejected
    with pytest.raises(ValidationError):
        Intervention(
            event_id="evt_bad",
            ingredient_id="saline",
            dose=-100.0,
            unit="mL",
            route="intravenous",
            simulation_time=0.0,
            idempotency_key="key"
        )


def test_simulation_config_contract():
    """Verify SimulationConfig validation."""
    config = SimulationConfig(
        run_id="run_999",
        engine_name="Pulse Physiology Engine",
        engine_version="4.4.0",
        profile_hash="sha256_mock_hash",
        horizon_seconds=600.0,
        sample_cadence_seconds=2.0
    )
    assert config.horizon_seconds == 600.0
    assert config.sample_cadence_seconds == 2.0


def test_physiology_snapshot_contract():
    """Verify PhysiologySnapshot contract and quantity schemas."""
    snapshot = PhysiologySnapshot(
        run_id="run_101",
        sequence=1,
        simulation_time=1.0,
        quantities={
            "heart_rate": {
                "value": 75.0,
                "unit": "bpm",
                "source": "pulse_engine",
                "capability": "engine_simulated"
            }
        },
        coverage_flags={"engine_simulated": "true"},
        is_valid=True
    )
    assert snapshot.sequence == 1
    assert snapshot.quantities["heart_rate"]["value"] == 75.0
    assert snapshot.quantities["heart_rate"].value == 75.0
    assert snapshot.quantities["heart_rate"]["unit"] == "bpm"


def test_agent_finding_contract():
    """Verify AgentFinding enforces allowed organ agents and severity ratings."""
    finding = AgentFinding(
        finding_id="find_001",
        run_id="run_001",
        sequence=5,
        simulation_time=120.0,
        organ="renal",
        category="perfusion",
        severity="monitor",
        inputs_observed={"map": 68.0, "gfr": 42.0},
        rule_id="RULE_RENAL_HYPOPERFUSION_01",
        coverage="engine_simulated",
        message="Renal perfusion below baseline threshold."
    )
    assert finding.organ == "renal"
    assert finding.severity == "monitor"

    # Reject unsupported organ agent name
    with pytest.raises(ValidationError):
        AgentFinding(
            finding_id="find_bad",
            run_id="run_001",
            sequence=1,
            simulation_time=0.0,
            organ="endocrine",  # not in core council
            category="glucose",
            severity="monitor",
            coverage="unsupported",
            message="Glucose check."
        )


def test_run_event_contract():
    """Verify RunEvent serialization and required fields."""
    event = RunEvent(
        run_id="run_001",
        sequence=0,
        simulation_time=0.0,
        wall_clock_time=1700000000.0,
        event_type="RUN_STARTED",
        payload={"profile_id": "pt_001"}
    )
    assert event.event_type == "RUN_STARTED"
    assert event.schema_version == "1.0.0"


def test_checkpoint_contract():
    """Verify Checkpoint contract."""
    checkpoint = Checkpoint(
        checkpoint_id="chk_001",
        run_id="run_001",
        simulation_time=60.0,
        sequence=60,
        serialized_engine_state='{"time": 60.0}',
        event_cursor=2,
        content_hash="abc123hash"
    )
    assert checkpoint.simulation_time == 60.0


def test_review_record_contract():
    """Verify ReviewRecord status literals and limitation acknowledgments."""
    review = ReviewRecord(
        review_id="rev_001",
        run_id="run_001",
        reviewer="Synthetic Clinical Auditor",
        timestamp=1700000100.0,
        status="approved",
        acknowledged_limitations=["NSAID effect is evidence-only; drug GFR trajectory not modeled."],
        notes="All invariants passed."
    )
    assert review.status == "approved"
    assert len(review.acknowledged_limitations) == 1


def test_json_schema_generation_for_all_models():
    """Ensure all core contracts produce compliant OpenAPI / JSON schemas."""
    models = [
        BaselineMeasurement,
        PatientProfile,
        Intervention,
        SimulationConfig,
        PhysiologySnapshot,
        AgentFinding,
        RunEvent,
        Checkpoint,
        ReviewRecord
    ]
    for model in models:
        schema = model.model_json_schema()
        assert "properties" in schema
        assert "title" in schema
