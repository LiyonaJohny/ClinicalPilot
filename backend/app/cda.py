"""C-CDA document ingestion: parse the XML with lxml into the shared patient model."""

from datetime import UTC, datetime
from typing import Any

from lxml import etree
from sqlalchemy.orm import Session

from .mapping import (
    CDA_SYSTEMS,
    LOINC_DIASTOLIC,
    LOINC_SYSTOLIC,
    MAX_AGE,
    ConditionFact,
    PatientDraft,
    classify_code,
    draft_to_row,
    parse_hl7_timestamp,
    plausible_bp,
)
from .persistence import patient_to_dict, save_ingestion_reject, upsert_patient
from .schemas import IngestResult, RejectedRecord

SOURCE = "cda"
HL7 = "urn:hl7-org:v3"
NS = {"hl7": HL7}

PROBLEM_SECTION_CODE = "11450-4"
VITALS_SECTION_CODE = "8716-3"
RESULTS_SECTION_CODE = "30954-2"
PROBLEM_SECTION_TEMPLATES = {"2.16.840.1.113883.10.20.22.2.5", "2.16.840.1.113883.10.20.22.2.5.1"}
VITALS_SECTION_TEMPLATES = {"2.16.840.1.113883.10.20.22.2.4", "2.16.840.1.113883.10.20.22.2.4.1"}
RESULTS_SECTION_TEMPLATES = {"2.16.840.1.113883.10.20.22.2.3", "2.16.840.1.113883.10.20.22.2.3.1"}
PROBLEM_OBSERVATION_TEMPLATE = "2.16.840.1.113883.10.20.22.4.4"
MAX_DOCUMENT_BYTES =25 * 1024 * 1024


class CdaError(ValueError):
    """The document cannot be ingested at all."""


def _parser() -> etree.XMLParser:
    # Entity resolution and network access stay off so an uploaded document cannot read local files or call out.
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False, recover=False)


def _sections(root: etree._Element, code: str, templates: set[str]) -> list[etree._Element]:
    found = []
    for section in root.iterfind(".//hl7:section", NS):
        section_code = section.find("hl7:code", NS)
        template_roots = {template.get("root") for template in section.iterfind("hl7:templateId", NS)}
        if (section_code is not None and section_code.get("code") == code) or template_roots & templates:
            found.append(section)
    return found


def _snippet(element: etree._Element) -> str:
    return etree.tostring(element, encoding="unicode")[:4000]


def _effective_time(observation: etree._Element) -> tuple[str | None, str | None]:
    """Return (start, end) raw TS values of an observation's effectiveTime."""
    effective = observation.find("hl7:effectiveTime", NS)
    if effective is None:
        return None, None
    low = effective.find("hl7:low", NS)
    high = effective.find("hl7:high", NS)
    start = effective.get("value") or (low.get("value") if low is not None else None)
    end = high.get("value") if high is not None else None
    return start, end


def _problem_fact(observation: etree._Element) -> ConditionFact | None:
    value = observation.find("hl7:value", NS)
    if value is None or not value.get("code"):
        return None
    candidates = [value, *value.iterfind("hl7:translation", NS)]
    system = CDA_SYSTEMS.get(value.get("codeSystem") or "", value.get("codeSystem"))
    code = value.get("code")
    flag = None
    for candidate in candidates:
        kind = CDA_SYSTEMS.get(candidate.get("codeSystem") or "")
        found = classify_code(kind, candidate.get("code"))
        if found:
            system, code, flag = kind, candidate.get("code"), found
            break
    start, end = _effective_time(observation)
    return ConditionFact(
        display=value.get("displayName") or code,
        system=system,
        code=code,
        flag=flag,
        onset=parse_hl7_timestamp(start),
        active=end is None,
    )


def parse_document(data: bytes) -> tuple[PatientDraft, list[tuple[RejectedRecord, str]], int, int]:
    """Parse a C-CDA document into a draft, the entries set aside, and mapped problem and observation counts."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise CdaError(f"document is larger than {MAX_DOCUMENT_BYTES} bytes")
    try:
        root = etree.fromstring(data, _parser())
    except etree.XMLSyntaxError as error:
        raise CdaError(f"not well-formed XML: {error}") from error
    if root.tag != f"{{{HL7}}}ClinicalDocument":
        raise CdaError("root element is not an HL7 v3 ClinicalDocument")

    role = root.find("hl7:recordTarget/hl7:patientRole", NS)
    if role is None:
        raise CdaError("recordTarget/patientRole is missing")
    patient_id = None
    for identifier in role.iterfind("hl7:id", NS):
        patient_id = identifier.get("extension") or identifier.get("root")
        if patient_id:
            break
    if not patient_id:
        raise CdaError("patientRole has no id with an extension or root")
    patient = role.find("hl7:patient", NS)
    if patient is None:
        raise CdaError("patientRole/patient is missing")
    birth_time = patient.find("hl7:birthTime", NS)
    birth = parse_hl7_timestamp(birth_time.get("value") if birth_time is not None else None)
    if birth is None:
        raise CdaError("patient birthTime is missing or not a valid HL7 timestamp")
    today = datetime.now(UTC).date()
    if birth.date() > today:
        raise CdaError("patient birthTime is in the future")
    if today.year - birth.year > MAX_AGE:
        raise CdaError(f"patient birthTime implies an age over {MAX_AGE}")

    gender = patient.find("hl7:administrativeGenderCode", NS)
    race = patient.find("hl7:raceCode", NS)
    draft = PatientDraft(
        patient_id=patient_id,
        source=SOURCE,
        birth_date=birth.date(),
        gender=gender.get("code") if gender is not None else None,
        race=race.get("displayName") if race is not None else None,
    )
    rejects: list[tuple[RejectedRecord, str]] = []

    def reject(resource_type: str, element: etree._Element, reason: str) -> None:
        identifier = element.find("hl7:id", NS)
        resource_id = (identifier.get("extension") or identifier.get("root")) if identifier is not None else None
        rejects.append((RejectedRecord(resource_type=resource_type, resource_id=resource_id, reason=reason), _snippet(element)))

    problems_mapped = 0
    for section in _sections(root, PROBLEM_SECTION_CODE, PROBLEM_SECTION_TEMPLATES):
        for entry in section.iterfind("hl7:entry", NS):
            candidates = [item for item in entry.iterfind(".//hl7:observation", NS) if item.find("hl7:value", NS) is not None]
            # Only Problem Observations are diagnoses; nested status and age observations are not.
            observations = [
                item
                for item in candidates
                if any(template.get("root") == PROBLEM_OBSERVATION_TEMPLATE for template in item.iterfind("hl7:templateId", NS))
            ] or candidates[:1]
            if not observations:
                reject("Problem", entry, "problem entry has no observation with a value")
                continue
            for observation in observations:
                fact = _problem_fact(observation)
                if fact is None:
                    reject("Problem", observation, "problem observation value has no code")
                    continue
                draft.conditions.append(fact)
                problems_mapped += 1

    observations_mapped = 0
    measured = [(section, True) for section in _sections(root, VITALS_SECTION_CODE, VITALS_SECTION_TEMPLATES)]
    measured += [(section, False) for section in _sections(root, RESULTS_SECTION_CODE, RESULTS_SECTION_TEMPLATES)]
    for section, is_vitals in measured:
        for observation in section.iterfind(".//hl7:observation", NS):
            code = observation.find("hl7:code", NS)
            loinc = code.get("code") if code is not None else None
            start, _ = _effective_time(observation)
            when = parse_hl7_timestamp(start)
            if start and when is None:
                reject("Observation", observation, f"effectiveTime {start!r} is not a valid HL7 timestamp")
                continue
            if is_vitals and loinc in (LOINC_SYSTOLIC, LOINC_DIASTOLIC):
                value = observation.find("hl7:value", NS)
                raw = value.get("value") if value is not None else None
                try:
                    reading = float(raw)
                except (TypeError, ValueError):
                    reject("Observation", observation, f"blood pressure value {raw!r} is not numeric")
                    continue
                if not plausible_bp(reading):
                    reject("Observation", observation, f"implausible blood pressure value {reading}")
                    continue
                if loinc == LOINC_SYSTOLIC:
                    draft.add_blood_pressure(when, reading, None)
                else:
                    draft.add_blood_pressure(when, None, reading)
            draft.note_observation(when)
            observations_mapped += 1

    return draft, rejects, problems_mapped, observations_mapped


def ingest_document(data: bytes, session: Session) -> IngestResult:
    """Parse a C-CDA document and upsert its patient. Raises CdaError when it cannot be ingested."""
    draft, rejects, problems_mapped, observations_mapped = parse_document(data)
    record = upsert_patient(session, draft_to_row(draft))
    for rejected, raw in rejects:
        save_ingestion_reject(session, SOURCE, rejected.resource_type, rejected.resource_id, rejected.reason, raw)
    return IngestResult(
        source=SOURCE,
        patients_ingested=1,
        conditions_mapped=problems_mapped,
        observations_mapped=observations_mapped,
        rejected_count=len(rejects),
        rejected=[rejected for rejected, _ in rejects],
        patients=[patient_to_dict(record)],
    )


def reject_document(session: Session, reason: str, data: bytes) -> None:
    payload: Any = data[:4000].decode("utf-8", errors="replace")
    save_ingestion_reject(session, SOURCE, "ClinicalDocument", None, reason, payload)
