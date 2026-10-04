"""
Gate 1 Feasibility & Capability Manifest Acceptance Tests.
Verifies engine adapter contract, snapshot schema, serialization/restore,
manifest correctness, and anti-fabrication rules.
"""

import os
import json
import pytest
from simulation.adapter import ReferenceTraceEngineAdapter
from simulation.capabilities import CapabilityLevel


@pytest.fixture
def manifest_data():
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "simulation",
        "capability-manifest.json"
    )
    assert os.path.exists(manifest_path), f"Manifest not found at {manifest_path}"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def initialized_engine(manifest_data):
    adapter = ReferenceTraceEngineAdapter(manifest=manifest_data)
    profile = {
        "run_id": "test_run_gate1",
        "age": 55,
        "sex": "male",
        "mass_kg": 70.0,
        "conditions": ["ChronicRenalStenosis"],
        "context": {"diabetes": True}
    }
    adapter.initialize(profile)
    return adapter


def test_capability_manifest_structure(manifest_data):
    """Manifest must contain metrics, conditions, and interventions per specification."""
    assert "schema_version" in manifest_data
    assert "metrics" in manifest_data
    assert "conditions" in manifest_data
    assert "interventions" in manifest_data

    # Check key metrics exist
    metrics = manifest_data["metrics"]
    assert "heart_rate" in metrics
    assert "mean_arterial_pressure" in metrics
    assert "glomerular_filtration_rate" in metrics
    assert "respiration_rate" in metrics
    assert "oxygen_saturation" in metrics

    # Check capability classifications
    assert metrics["mean_arterial_pressure"]["capability"] == CapabilityLevel.ILLUSTRATIVE.value
    assert metrics["alt_ast_levels"]["capability"] == CapabilityLevel.UNSUPPORTED.value
    assert metrics["blood_glucose"]["capability"] == CapabilityLevel.UNSUPPORTED.value

    # Check conditions
    conditions = manifest_data["conditions"]
    assert conditions["ChronicRenalStenosis"]["capability"] == CapabilityLevel.UNSUPPORTED.value
    assert conditions["CKD"]["capability"] == CapabilityLevel.EVIDENCE_ONLY.value
    assert conditions["CKD"]["engine_mapping"] is None
    assert conditions["Type2DiabetesMellitus"]["capability"] == CapabilityLevel.UNSUPPORTED.value

    # Check interventions
    interventions = manifest_data["interventions"]
    assert interventions["Dehydration"]["capability"] == CapabilityLevel.ILLUSTRATIVE.value
    assert interventions["High_Dose_NSAID"]["capability"] == CapabilityLevel.EVIDENCE_ONLY.value
    assert interventions["High_Dose_NSAID"]["numerical_effect"] is False


def test_engine_initialization_and_baseline(initialized_engine):
    """Unmodeled conditions remain context and cannot fabricate disease-specific vitals."""
    assert initialized_engine.is_initialized is True
    comparison = ReferenceTraceEngineAdapter()
    comparison.initialize({})
    assert initialized_engine.snapshot()["quantities"] == comparison.snapshot()["quantities"]
    assert "ChronicRenalStenosis" in initialized_engine.snapshot()["coverage_flags"]["context_only_conditions"]


def test_engine_advance_and_snapshot(initialized_engine):
    """Engine advance must update simulation time and generate compliant snapshot."""
    initialized_engine.advance(30.0)
    assert initialized_engine.simulation_time == 30.0
    assert initialized_engine.sequence == 1

    snap = initialized_engine.snapshot()
    assert snap["simulation_time"] == 30.0
    assert snap["sequence"] == 1
    assert "quantities" in snap
    assert snap["quantities"]["heart_rate"]["unit"] == "bpm"
    assert snap["is_valid"] is True
    assert snap["numerical_error_code"] is None
    assert snap["coverage_flags"]["physiology_engine_verified"] is False


def test_engine_serialize_and_restore(initialized_engine):
    """Engine checkpoint must serialize to string and restore perfectly."""
    initialized_engine.advance(45.0)
    checkpoint = initialized_engine.serialize()
    assert isinstance(checkpoint, str)

    new_engine = ReferenceTraceEngineAdapter()
    success = new_engine.restore(checkpoint)
    assert success is True
    assert new_engine.simulation_time == 45.0
    assert new_engine.state["heart_rate"] == initialized_engine.state["heart_rate"]
    assert new_engine.state["mean_arterial_pressure"] == initialized_engine.state["mean_arterial_pressure"]


def test_anti_fabrication_rule_for_evidence_only(initialized_engine):
    """Rule 3/Constraint 3: Evidence-only medication (NSAID) must NOT mutate numerical vitals."""
    nsaid_event = {
        "event_id": "evt_nsaid_test",
        "type": "medication",
        "name": "High-Dose Ibuprofen",
        "ingredient_id": "ibuprofen",
        "dose": 800.0,
        "unit": "mg",
        "route": "oral",
        "simulation_time": 0.0
    }
    applied = initialized_engine.apply_event(nsaid_event)
    assert applied is True

    # Advance without stressors
    gfr_prior = initialized_engine.state["glomerular_filtration_rate"]
    map_prior = initialized_engine.state["mean_arterial_pressure"]
    initialized_engine.advance(60.0)

    # State must not have changed because ibuprofen is EVIDENCE_ONLY (no fabricated drug trajectory)
    assert initialized_engine.state["glomerular_filtration_rate"] == gfr_prior
    assert initialized_engine.state["mean_arterial_pressure"] == map_prior
