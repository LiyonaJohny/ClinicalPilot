"""Pydantic models for the FHIR R4 resources ClinicalPilot ingests.

These cover the subset of each resource that ingestion reads. Unknown fields
are allowed, so a full Synthea resource validates without listing every element.
"""

from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .mapping import MAX_AGE, parse_fhir_datetime

OBSERVATION_STATUSES = (
    "registered",
    "preliminary",
    "final",
    "amended",
    "corrected",
    "cancelled",
    "entered-in-error",
    "unknown",
)


class FhirModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Coding(FhirModel):
    system: str | None = None
    code: str | None = None
    display: str | None = None


class CodeableConcept(FhirModel):
    coding: list[Coding] = Field(default_factory=list)
    text: str | None = None

    @model_validator(mode="after")
    def has_code_or_text(self) -> "CodeableConcept":
        if not self.text and not any(coding.code for coding in self.coding):
            raise ValueError("must contain a coding with a code, or text")
        return self

    def label(self) -> str:
        if self.text:
            return self.text
        for coding in self.coding:
            if coding.display:
                return coding.display
        return next(coding.code for coding in self.coding if coding.code)


class Reference(FhirModel):
    reference: str = Field(min_length=1)


class Quantity(FhirModel):
    value: float | None = None
    unit: str | None = None


class Extension(FhirModel):
    url: str
    valueString: str | None = None
    valueCoding: Coding | None = None
    extension: list["Extension"] = Field(default_factory=list)


class Patient(FhirModel):
    resourceType: Literal["Patient"]
    id: str = Field(min_length=1)
    gender: Literal["male", "female", "other", "unknown"] | None = None
    birthDate: date
    deceasedDateTime: str | None = None
    extension: list[Extension] = Field(default_factory=list)

    @field_validator("birthDate", mode="before")
    @classmethod
    def parse_birth_date(cls, value: Any) -> Any:
        # FHIR allows partial dates (YYYY or YYYY-MM); pin them to the first day.
        if isinstance(value, str):
            parsed = parse_fhir_datetime(value)
            if parsed is None:
                raise ValueError("not a valid FHIR date")
            return parsed.date()
        return value

    @field_validator("birthDate")
    @classmethod
    def plausible_birth_date(cls, value: date) -> date:
        today = datetime.now(UTC).date()
        if value > today:
            raise ValueError("is in the future")
        if today.year - value.year > MAX_AGE:
            raise ValueError(f"implies an age over {MAX_AGE}")
        return value


class Condition(FhirModel):
    resourceType: Literal["Condition"]
    id: str | None = None
    subject: Reference
    code: CodeableConcept
    clinicalStatus: CodeableConcept | None = None
    verificationStatus: CodeableConcept | None = None
    onsetDateTime: str | None = None
    recordedDate: str | None = None
    abatementDateTime: str | None = None


class ObservationComponent(FhirModel):
    code: CodeableConcept
    valueQuantity: Quantity | None = None


class Observation(FhirModel):
    resourceType: Literal["Observation"]
    id: str | None = None
    status: Literal[OBSERVATION_STATUSES]
    subject: Reference
    code: CodeableConcept
    effectiveDateTime: str | None = None
    issued: str | None = None
    valueQuantity: Quantity | None = None
    component: list[ObservationComponent] = Field(default_factory=list)


class BundleEntry(FhirModel):
    fullUrl: str | None = None
    resource: dict[str, Any] | None = None


class Bundle(FhirModel):
    resourceType: Literal["Bundle"]
    type: str | None = None
    entry: list[BundleEntry] = Field(default_factory=list)


class RejectedRecord(BaseModel):
    resource_type: str
    resource_id: str | None = None
    reason: str


class IngestResult(BaseModel):
    source: Literal["fhir", "cda"]
    patients_ingested: int
    conditions_mapped: int
    observations_mapped: int
    rejected_count: int
    rejected: list[RejectedRecord]
    skipped_resource_types: dict[str, int] = Field(default_factory=dict)
    patients: list[dict[str, Any]]
