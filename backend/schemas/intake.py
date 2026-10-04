from typing import Literal, Optional

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from backend.schemas.domain import DomainModel, FiniteNumber

HistoryStatus = Literal["none_known", "conditions", "unknown"]


class PatientInput(DomainModel):
    name: Optional[StrictStr] = Field(default=None, max_length=160)
    age: StrictInt = Field(gt=0, lt=130)
    gender: Literal["male", "female", "woman", "man", "non_binary", "self_described", "prefer_not_to_say"]
    gender_detail: StrictStr = Field(default="", max_length=120)
    sex: Optional[Literal["male", "female"]] = None
    mass_kg: Optional[FiniteNumber] = Field(default=None, gt=0, lt=350)
    allergies_status: HistoryStatus
    allergies: list[StrictStr] = Field(default_factory=list, max_length=24)
    current_medications_status: HistoryStatus
    current_medications: list[StrictStr] = Field(default_factory=list, max_length=24)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return value.strip() or None if value is not None else None

    @field_validator("allergies", "current_medications")
    @classmethod
    def clean_entries(cls, values):
        if any(not value.strip() or len(value) > 160 for value in values):
            raise ValueError("Entries must contain 1-160 characters")
        return [value.strip() for value in values]

    @model_validator(mode="after")
    def history_consistency(self):
        for key in ("allergies", "current_medications"):
            entries = getattr(self, key)
            status = getattr(self, key + "_status")
            if (status == "conditions") != bool(entries):
                raise ValueError(f"{key}: a recorded history requires a list; none/unknown requires an empty list")
        return self


class SelectedCondition(DomainModel):
    condition_id: StrictStr = Field(min_length=1, max_length=120)
    severity: StrictStr = Field(default="unknown", max_length=40)
    subtype: StrictStr = Field(default="unknown", max_length=60)
    notes: StrictStr = Field(default="", max_length=300)


class OrganInput(DomainModel):
    status: HistoryStatus
    conditions: list[SelectedCondition] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def consistency(self):
        if (self.status == "conditions") != bool(self.conditions):
            raise ValueError("Known conditions require a selection; none/unknown requires an empty list")
        identifiers = [condition.condition_id for condition in self.conditions]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("A condition cannot be selected twice in one system")
        return self


class BloodPressureInput(DomainModel):
    status: Literal["none_known", "hypertension", "hypotension", "other", "unknown"]
    control: Literal["controlled", "uncontrolled", "unknown"] = "unknown"
    notes: StrictStr = Field(default="", max_length=300)
    systolic: Optional[FiniteNumber] = Field(default=None, gt=0, le=400)
    diastolic: Optional[FiniteNumber] = Field(default=None, gt=0, le=300)
    observed_at: StrictStr = Field(default="", max_length=80)

    @model_validator(mode="after")
    def check_reading(self):
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("Enter both systolic and diastolic pressure, or leave both blank")
        if self.systolic is not None and self.diastolic >= self.systolic:
            raise ValueError("Systolic pressure must exceed diastolic pressure")
        if self.status != "hypertension" and self.control != "unknown":
            raise ValueError("Control status applies only to hypertension")
        return self


class MedicationInput(DomainModel):
    drug_id: StrictStr = Field(min_length=1, max_length=80)
    dose: FiniteNumber = Field(gt=0, le=1000000000)
    unit: Literal["mg", "g", "mcg", "mL", "L"]
    route: Literal["oral", "intravenous", "intramuscular", "subcutaneous", "rectal", "inhaled"]
    time_seconds: FiniteNumber = Field(default=0, ge=0, le=3600)
    duration_seconds: FiniteNumber = Field(default=0, ge=0, le=3600)
    repeat_count: StrictInt = Field(default=1, ge=1, le=20)
    interval_seconds: FiniteNumber = Field(default=0, ge=0, le=3600)


class MeasurementInput(DomainModel):
    name: StrictStr = Field(min_length=1, max_length=80)
    value: FiniteNumber
    unit: StrictStr = Field(min_length=1, max_length=40)
    observed_at: StrictStr = Field(default="", max_length=80)
    source: StrictStr = Field(default="user_entered", max_length=80)


class PatientIntake(DomainModel):
    patient: PatientInput
    organs: dict[Literal["cardiovascular", "renal", "hepatic", "respiratory"], OrganInput]
    blood_pressure: BloodPressureInput
    medications: list[MedicationInput] = Field(min_length=1, max_length=24)
    measurements: list[MeasurementInput] = Field(default_factory=list, max_length=32)
    horizon_seconds: FiniteNumber = Field(default=300, ge=10, le=3600)

    @model_validator(mode="after")
    def complete_systems(self):
        if set(self.organs) != {"cardiovascular", "renal", "hepatic", "respiratory"}:
            raise ValueError("All four systems require an explicit history response")
        if sum(len(organ.conditions) for organ in self.organs.values()) > 32:
            raise ValueError("At most 32 conditions can be recorded per assessment")
        return self
