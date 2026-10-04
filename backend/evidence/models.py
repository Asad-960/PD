from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field

class EvidenceSource(BaseModel):
    source_id: str = Field(..., description="Unique identifier for the evidence source")
    title: str = Field(..., description="Title of the source document or guideline")
    url: str = Field(..., description="URL to the source")
    publication_date: str = Field(..., description="Date of publication (e.g., YYYY-MM-DD)")
    license: str = Field(..., description="License of the source material")
    raw_extract: str = Field(..., description="Relevant extracted text supporting the rule")

class Precondition(BaseModel):
    required_conditions: List[str] = Field(
        default_factory=list,
        description="Clinical conditions or aliases required to trigger the rule (e.g., ['ChronicRenalStenosis'])"
    )
    required_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Patient context flags required (e.g., {'hepatic_impairment': 'moderate'})"
    )
    trigger_interventions: List[str] = Field(
        default_factory=list,
        description="Interventions/ingredients that trigger the rule (e.g., ['High_Dose_NSAID', 'ibuprofen'])"
    )
    hemodynamic_thresholds: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Snapshot quantity thresholds (e.g., {'mean_arterial_pressure': {'max': 70.0}})"
    )
    required_measurements: List[str] = Field(
        default_factory=list,
        description="Baseline measurements required for evaluation (e.g., ['egfr', 'creatinine'])"
    )

class EvidenceRule(BaseModel):
    rule_id: str = Field(..., description="Unique rule identifier")
    version: str = Field(..., description="Semantic version of the rule")
    target_organ: Literal["renal", "cardiovascular", "hepatic", "respiratory"] = Field(
        ..., description="Primary organ domain affected"
    )
    category: str = Field(..., description="Clinical category of the finding")
    severity: Literal["normal", "monitor", "critical", "unknown"] = Field(
        ..., description="Severity level if the rule fires"
    )
    ingredient_or_class: str = Field(..., description="Drug ingredient or class involved")
    mechanism: str = Field(..., description="Physiological mechanism of the rule")
    preconditions: Precondition = Field(..., description="Preconditions that must be met to fire")
    source_id: str = Field(..., description="Reference to EvidenceSource source_id")
    source_section: str = Field(..., description="Specific section or page in the source")
    review_status: Literal["reviewed", "draft", "unreviewed"] = Field(
        ..., description="Status of the rule in the registry"
    )
    limitations: str = Field(..., description="Explicit limitations of the rule/engine modeling")
    user_message: str = Field(..., description="Message presented to the user when fired")
