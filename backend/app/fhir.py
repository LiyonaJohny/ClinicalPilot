"""FHIR R4 Bundle ingestion: validate each resource, map valid ones, set aside the rest."""

from collections import Counter
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from .mapping import (
    FHIR_SYSTEMS,
    LOINC,
    LOINC_BP_PANEL,
    LOINC_DIASTOLIC,
    LOINC_SYSTOLIC,
    ConditionFact,
    PatientDraft,
    classify_code,
    draft_to_row,
    parse_fhir_datetime,
    plausible_bp,
)
from .persistence import patient_to_dict, save_ingestion_reject, upsert_patient
from .schemas import Bundle, CodeableConcept, Condition, Extension, IngestResult, Observation, Patient, RejectedRecord

SOURCE = "fhir"
US_CORE_RACE = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
INACTIVE_CLINICAL_STATUSES = {"inactive", "resolved", "remission"}
INVALID_VERIFICATION_STATUSES = {"refuted", "entered-in-error"}
IGNORED_OBSERVATION_STATUSES = {"cancelled", "entered-in-error"}
MAX_REJECTS_IN_RESPONSE = 100


class BundleError(ValueError):
    """The payload is not a usable FHIR Bundle at all."""


def describe_validation_error(error: ValidationError) -> str:
    parts = []
    for issue in error.errors():
        location = ".".join(str(item) for item in issue["loc"]) or "resource"
        parts.append(f"{location}: {issue['msg']}")
    return "; ".join(parts)


def _status_codes(concept: CodeableConcept | None) -> set[str]:
    return {coding.code for coding in concept.coding if coding.code} if concept else set()


def _loinc_codes(concept: CodeableConcept) -> set[str]:
    return {coding.code for coding in concept.coding if coding.code and FHIR_SYSTEMS.get(coding.system or "") == LOINC}


def _race(extensions: list[Extension]) -> str | None:
    for extension in extensions:
        if extension.url != US_CORE_RACE:
            continue
        for nested in extension.extension:
            if nested.url == "text" and nested.valueString:
                return nested.valueString
        for nested in extension.extension:
            if nested.url == "ombCategory" and nested.valueCoding and nested.valueCoding.display:
                return nested.valueCoding.display
    return None


def _condition_fact(condition: Condition) -> ConditionFact:
    system = code = flag = None
    for coding in condition.code.coding:
        kind = FHIR_SYSTEMS.get(coding.system or "")
        found = classify_code(kind, coding.code)
        if system is None or found:
            system, code = kind or coding.system, coding.code
        if found:
            flag = found
            break
    active = not (_status_codes(condition.clinicalStatus) & INACTIVE_CLINICAL_STATUSES) and condition.abatementDateTime is None
    return ConditionFact(
        display=condition.code.label(),
        system=system,
        code=code,
        flag=flag,
        onset=parse_fhir_datetime(condition.onsetDateTime or condition.recordedDate),
        active=active,
    )


def _blood_pressure(observation: Observation) -> tuple[float | None, float | None]:
    """Systolic and diastolic values carried by an observation, if it is a BP reading."""
    systolic = diastolic = None
    codes = _loinc_codes(observation.code)
    if LOINC_SYSTOLIC in codes and observation.valueQuantity:
        systolic = observation.valueQuantity.value
    if LOINC_DIASTOLIC in codes and observation.valueQuantity:
        diastolic = observation.valueQuantity.value
    if LOINC_BP_PANEL in codes or observation.component:
        for component in observation.component:
            component_codes = _loinc_codes(component.code)
            if component.valueQuantity is None:
                continue
            if LOINC_SYSTOLIC in component_codes:
                systolic = component.valueQuantity.value
            if LOINC_DIASTOLIC in component_codes:
                diastolic = component.valueQuantity.value
    return systolic, diastolic


class _Ingestion:
    def __init__(self) -> None:
        self.drafts: dict[str, PatientDraft] = {}
        self.references: dict[str, str] = {}
        self.rejects: list[tuple[RejectedRecord, Any]] = []
        self.skipped: Counter[str] = Counter()
        self.conditions_mapped = 0
        self.observations_mapped = 0

    def reject(self, resource_type: str, resource_id: Any, reason: str, payload: Any) -> None:
        resource_id = resource_id if isinstance(resource_id, str) and resource_id else None
        self.rejects.append((RejectedRecord(resource_type=resource_type, resource_id=resource_id, reason=reason), payload))

    def resolve(self, reference: str) -> PatientDraft | None:
        patient_id = self.references.get(reference)
        if patient_id is None and "Patient/" in reference:
            patient_id = self.references.get("Patient/" + reference.rsplit("Patient/", 1)[1])
        return self.drafts.get(patient_id) if patient_id else None

    def add_patient(self, resource: dict[str, Any], full_url: str | None) -> None:
        try:
            patient = Patient.model_validate(resource)
        except ValidationError as error:
            self.reject("Patient", resource.get("id"), describe_validation_error(error), resource)
            return
        if patient.id in self.drafts:
            self.reject("Patient", patient.id, "duplicate Patient id in bundle", resource)
            return
        deceased = parse_fhir_datetime(patient.deceasedDateTime)
        self.drafts[patient.id] = PatientDraft(
            patient_id=patient.id,
            source=SOURCE,
            birth_date=patient.birthDate,
            gender=patient.gender,
            race=_race(patient.extension),
            deceased_on=deceased.date() if deceased else None,
        )
        for key in (full_url, f"Patient/{patient.id}", f"urn:uuid:{patient.id}", patient.id):
            if key:
                self.references[key] = patient.id

    def add_condition(self, resource: dict[str, Any]) -> None:
        try:
            condition = Condition.model_validate(resource)
        except ValidationError as error:
            self.reject("Condition", resource.get("id"), describe_validation_error(error), resource)
            return
        draft = self.resolve(condition.subject.reference)
        if draft is None:
            self.reject("Condition", condition.id, f"subject {condition.subject.reference} does not match a valid Patient in this bundle", resource)
            return
        if _status_codes(condition.verificationStatus) & INVALID_VERIFICATION_STATUSES:
            self.reject("Condition", condition.id, "verificationStatus is refuted or entered-in-error", resource)
            return
        draft.conditions.append(_condition_fact(condition))
        self.conditions_mapped += 1

    def add_observation(self, resource: dict[str, Any]) -> None:
        try:
            observation = Observation.model_validate(resource)
        except ValidationError as error:
            self.reject("Observation", resource.get("id"), describe_validation_error(error), resource)
            return
        draft = self.resolve(observation.subject.reference)
        if draft is None:
            self.reject("Observation", observation.id, f"subject {observation.subject.reference} does not match a valid Patient in this bundle", resource)
            return
        if observation.status in IGNORED_OBSERVATION_STATUSES:
            self.reject("Observation", observation.id, f"status is {observation.status}", resource)
            return
        raw_when = observation.effectiveDateTime or observation.issued
        when = parse_fhir_datetime(raw_when)
        if raw_when and when is None:
            self.reject("Observation", observation.id, f"effective time {raw_when!r} is not a valid FHIR dateTime", resource)
            return
        systolic, diastolic = _blood_pressure(observation)
        for label, value in (("systolic", systolic), ("diastolic", diastolic)):
            if value is not None and not plausible_bp(value):
                self.reject("Observation", observation.id, f"implausible {label} blood pressure value {value}", resource)
                return
        if systolic is not None or diastolic is not None:
            draft.add_blood_pressure(when, systolic, diastolic)
        draft.note_observation(when)
        self.observations_mapped += 1


def ingest_bundle(payload: Any, session: Session) -> IngestResult:
    """Validate a FHIR R4 Bundle and upsert its patients.

    Invalid resources are stored in ingestion_rejects with the reason and do not
    stop the rest of the bundle. Raises BundleError when the payload is not a Bundle.
    """
    try:
        bundle = Bundle.model_validate(payload)
    except ValidationError as error:
        reason = describe_validation_error(error)
        save_ingestion_reject(session, SOURCE, "Bundle", None, reason, payload if isinstance(payload, (dict, list)) else str(payload))
        raise BundleError(reason) from error

    run = _Ingestion()
    typed: list[tuple[str, dict[str, Any], str | None]] = []
    for index, entry in enumerate(bundle.entry):
        resource = entry.resource
        resource_type = resource.get("resourceType") if resource else None
        if not resource or not isinstance(resource_type, str) or not resource_type:
            run.reject("Unknown", None, f"entry[{index}] has no resource with a resourceType", entry.model_dump())
            continue
        typed.append((resource_type, resource, entry.fullUrl))

    # Patients first, so Conditions and Observations can resolve their subject in any entry order.
    for resource_type, resource, full_url in typed:
        if resource_type == "Patient":
            run.add_patient(resource, full_url)
    for resource_type, resource, _ in typed:
        if resource_type == "Condition":
            run.add_condition(resource)
        elif resource_type == "Observation":
            run.add_observation(resource)
        elif resource_type != "Patient":
            run.skipped[resource_type] += 1

    records = [upsert_patient(session, draft_to_row(draft)) for draft in run.drafts.values()]
    for rejected, raw in run.rejects:
        save_ingestion_reject(session, SOURCE, rejected.resource_type, rejected.resource_id, rejected.reason, raw)

    return IngestResult(
        source=SOURCE,
        patients_ingested=len(records),
        conditions_mapped=run.conditions_mapped,
        observations_mapped=run.observations_mapped,
        rejected_count=len(run.rejects),
        rejected=[rejected for rejected, _ in run.rejects[:MAX_REJECTS_IN_RESPONSE]],
        skipped_resource_types=dict(sorted(run.skipped.items())),
        patients=[patient_to_dict(record) for record in records],
    )
