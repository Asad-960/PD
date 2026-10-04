"""Strict active-adapter capabilities and exact identifiers shared by consumers."""
import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

class CapabilityLevel(str, Enum):
    ENGINE_SIMULATED = "engine_simulated"
    EVIDENCE_ONLY = "evidence_only"
    ILLUSTRATIVE = "illustrative"
    UNSUPPORTED = "unsupported"

class OrganDomain(str, Enum):
    CARDIOVASCULAR = "cardiovascular"
    RENAL = "renal"
    RESPIRATORY = "respiratory"
    HEPATIC = "hepatic"
    METABOLIC = "metabolic"

class StrictCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

class MetricCapability(StrictCapability):
    name: str
    display_name: str
    unit: str
    domain: OrganDomain
    capability: CapabilityLevel
    description: str
    notes: Optional[str] = None

class ConditionCapability(StrictCapability):
    name: str
    engine_mapping: Optional[str] = None
    capability: CapabilityLevel
    target_organs: List[OrganDomain]
    severity_range: Optional[str] = None
    notes: Optional[str] = None

class InterventionCapability(StrictCapability):
    name: str
    ingredient_or_type: str
    route: Optional[str] = None
    capability: CapabilityLevel
    target_organs: List[OrganDomain]
    numerical_effect: bool
    evidence_effect: bool
    notes: Optional[str] = None

class CapabilityManifest(StrictCapability):
    schema_version: str
    engine_name: str
    engine_version: str
    engine_available_locally: bool
    execution_mode: Literal["ILLUSTRATIVE", "NATIVE_ENGINE", "REFERENCE_TRACE_REPLAY"]
    physiology_engine_verified: bool
    evidence_verified: bool
    provenance_statement: str
    limitations: List[str]
    metrics: Dict[str, MetricCapability] = Field(default_factory=dict)
    conditions: Dict[str, ConditionCapability] = Field(default_factory=dict)
    interventions: Dict[str, InterventionCapability] = Field(default_factory=dict)

CONDITION_ALIASES = {
    "ckd": "CKD", "chronic_kidney_disease": "CKD", "impaired_renal_function": "CKD",
    "chf": "ChronicVentricularSystolicDysfunction",
    "chronic_heart_failure": "ChronicVentricularSystolicDysfunction",
    "heart_failure": "ChronicVentricularSystolicDysfunction",
    "copd": "ChronicObstructivePulmonaryDisease",
    "hypertension": "EssentialHypertension", "htn": "EssentialHypertension",
    "high_blood_pressure": "EssentialHypertension", "anemia": "ChronicAnemia",
    "chronic_anemia": "ChronicAnemia", "diabetes": "Type2DiabetesMellitus",
    "t2d": "Type2DiabetesMellitus", "type_2_diabetes": "Type2DiabetesMellitus",
    "type2diabetes": "Type2DiabetesMellitus", "cirrhosis": "HepaticCirrhosis",
    "liver_cirrhosis": "HepaticCirrhosis", "hepatic_impairment": "HepaticCirrhosis",
}
INTERVENTION_ALIASES = {
    "dehydration": "Dehydration", "volume_depletion": "Dehydration",
    "saline": "IV_Saline_Infusion", "saline_0.9": "IV_Saline_Infusion",
    "normal_saline": "IV_Saline_Infusion", "iv_saline": "IV_Saline_Infusion",
    "ibuprofen": "High_Dose_NSAID", "nsaid": "High_Dose_NSAID",
    "high_dose_nsaid": "High_Dose_NSAID", "high-dose nsaid": "High_Dose_NSAID",
    "norepinephrine": "Vasopressor_Norepinephrine", "vasopressor": "Vasopressor_Norepinephrine",
    "morphine": "Morphine", "fentanyl": "Fentanyl", "opioid": "Opioid_Bolus",
    "lisinopril": "ACE_Inhibitor", "acei": "ACE_Inhibitor", "ace_inhibitor": "ACE_Inhibitor",
    "oxygen": "Supplemental_Oxygen", "supplemental_o2": "Supplemental_Oxygen",
    "naloxone": "Naloxone_Rescue", "narcan": "Naloxone_Rescue",
}

def canonical_identifier(value: str, aliases: Dict[str, str], items: Dict) -> Optional[str]:
    """Resolve explicit aliases/identifiers, never a substring or event ID."""
    normalized = value.strip().lower()
    candidate = aliases.get(normalized)
    if candidate in items:
        return candidate
    return next((key for key in items if key.lower() == normalized), None)

def load_manifest(path: Optional[str] = None) -> CapabilityManifest:
    location = Path(path) if path is not None else Path(__file__).with_name("capability-manifest.json")
    return CapabilityManifest.model_validate(json.loads(location.read_text(encoding="utf-8")))
