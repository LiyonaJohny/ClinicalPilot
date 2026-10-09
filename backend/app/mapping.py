"""Shared clinical mapping used by the FHIR and CDA ingestion paths.

Both formats are reduced to a PatientDraft, which is then flattened into the
row layout of the patients table (the same columns as the sample CSV).
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

SNOMED = "snomed"
ICD10 = "icd10"
LOINC = "loinc"

FHIR_SYSTEMS = {
    "http://snomed.info/sct": SNOMED,
    "http://hl7.org/fhir/sid/icd-10-cm": ICD10,
    "http://hl7.org/fhir/sid/icd-10": ICD10,
    "http://loinc.org": LOINC,
}

CDA_SYSTEMS = {
    "2.16.840.1.113883.6.96": SNOMED,
    "2.16.840.1.113883.6.90": ICD10,
    "2.16.840.1.113883.6.3": ICD10,
    "2.16.840.1.113883.6.1": LOINC,
}

LOINC_BP_PANEL = "85354-9"
LOINC_SYSTOLIC = "8480-6"
LOINC_DIASTOLIC = "8462-4"

DIABETES_TYPE2 = "diabetes_type2"
HYPERTENSION = "hypertension"
KIDNEY_DISEASE = "kidney_disease"

FLAG_LABELS = {
    DIABETES_TYPE2: "Diabetes T2",
    HYPERTENSION: "Hypertension",
    KIDNEY_DISEASE: "Kidney Disease",
}

SNOMED_FLAGS = {
    "44054006": DIABETES_TYPE2,  # Diabetes mellitus type 2
    "59621000": HYPERTENSION,  # Essential hypertension
    "38341003": HYPERTENSION,  # Hypertensive disorder, systemic arterial
    "709044004": KIDNEY_DISEASE,  # Chronic kidney disease
    "431855005": KIDNEY_DISEASE,  # Chronic kidney disease stage 1
    "431856006": KIDNEY_DISEASE,  # Chronic kidney disease stage 2
    "433144002": KIDNEY_DISEASE,  # Chronic kidney disease stage 3
    "431857002": KIDNEY_DISEASE,  # Chronic kidney disease stage 4
    "433146000": KIDNEY_DISEASE,  # Chronic kidney disease stage 5
    "46177005": KIDNEY_DISEASE,  # End-stage renal disease
    "127013003": KIDNEY_DISEASE,  # Disorder of kidney due to diabetes mellitus
}

ICD10_PREFIX_FLAGS = (
    ("E11", DIABETES_TYPE2),
    ("I10", HYPERTENSION),
    ("I11", HYPERTENSION),
    ("I12", HYPERTENSION),
    ("I13", HYPERTENSION),
    ("I15", HYPERTENSION),
    ("I16", HYPERTENSION),
    ("N18", KIDNEY_DISEASE),
)

GENDER_LABELS = {
    "male": "M",
    "m": "M",
    "female": "F",
    "f": "F",
    "other": "Other",
}

MIN_BP = 20.0
MAX_BP = 400.0
MAX_AGE = 130


def classify_code(system: str | None, code: str | None) -> str | None:
    """Return the chronic-condition flag a coded diagnosis maps to, if any."""
    if not system or not code:
        return None
    code = code.strip()
    if system == SNOMED:
        return SNOMED_FLAGS.get(code)
    if system == ICD10:
        normalized = code.upper()
        for prefix, flag in ICD10_PREFIX_FLAGS:
            if normalized.startswith(prefix):
                return flag
    return None


def gender_label(value: str | None) -> str:
    return GENDER_LABELS.get((value or "").strip().lower(), "Unknown")


def age_on(birth_date: date, on: date) -> int:
    years = on.year - birth_date.year
    if (on.month, on.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def parse_fhir_datetime(value: str | None) -> datetime | None:
    """Parse a FHIR date or dateTime (YYYY, YYYY-MM, YYYY-MM-DD or full ISO 8601)."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    try:
        if len(value) == 4:
            parsed = datetime(int(value), 1, 1)
        elif len(value) == 7:
            parsed = datetime(int(value[:4]), int(value[5:7]), 1)
        else:
            parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def parse_hl7_timestamp(value: str | None) -> datetime | None:
    """Parse an HL7 v3 TS value: YYYY[MM[DD[HH[MM[SS]]]]] with an optional +ZZZZ offset."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    offset = ""
    for sign in ("+", "-"):
        position = value.find(sign)
        if position > 0:
            value, offset = value[:position], value[position:]
            break
    value = value.split(".")[0]
    if not value.isdigit() or len(value) not in (4, 6, 8, 10, 12, 14):
        return None
    if len(value) == 4:
        value += "0101"
    elif len(value) == 6:
        value += "01"
    value = value.ljust(14, "0")
    try:
        if offset:
            return datetime.strptime(value + offset, "%Y%m%d%H%M%S%z").astimezone(UTC)
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


@dataclass
class ConditionFact:
    display: str
    system: str | None
    code: str | None
    flag: str | None
    onset: datetime | None
    active: bool


@dataclass
class PatientDraft:
    patient_id: str
    source: str
    birth_date: date
    gender: str | None = None
    race: str | None = None
    deceased_on: date | None = None
    conditions: list[ConditionFact] = field(default_factory=list)
    # Blood pressure readings keyed by effective time; None means the reading was undated.
    blood_pressure: dict[datetime | None, dict[str, float]] = field(default_factory=dict)
    last_observation: datetime | None = None

    def add_blood_pressure(self, when: datetime | None, systolic: float | None, diastolic: float | None) -> None:
        reading = self.blood_pressure.setdefault(when, {})
        if systolic is not None:
            reading["systolic"] = systolic
        if diastolic is not None:
            reading["diastolic"] = diastolic

    def note_observation(self, when: datetime | None) -> None:
        if when is not None and (self.last_observation is None or when > self.last_observation):
            self.last_observation = when


def plausible_bp(value: float) -> bool:
    return MIN_BP <= value <= MAX_BP


def _latest_reading(draft: PatientDraft) -> dict[str, float]:
    dated = sorted((when for when in draft.blood_pressure if when is not None), reverse=True)
    for when in dated:
        if "systolic" in draft.blood_pressure[when]:
            return draft.blood_pressure[when]
    if dated:
        return draft.blood_pressure[dated[0]]
    return draft.blood_pressure.get(None, {})


def draft_to_row(draft: PatientDraft, today: date | None = None) -> dict[str, Any]:
    """Flatten a draft into the column values of the patients table."""
    today = today or datetime.now(UTC).date()
    active = [fact for fact in draft.conditions if fact.active]
    flags = {fact.flag for fact in active if fact.flag}
    labels = [label for flag, label in FLAG_LABELS.items() if flag in flags]
    if labels:
        diagnosis = "; ".join(labels)
    elif active:
        latest = max(active, key=lambda fact: fact.onset or datetime.min.replace(tzinfo=UTC))
        diagnosis = latest.display
    else:
        diagnosis = "N/A"
    reading = _latest_reading(draft)
    return {
        "patient_id": draft.patient_id,
        "source": draft.source,
        "birth_date": draft.birth_date,
        "age": age_on(draft.birth_date, draft.deceased_on or today),
        "gender": gender_label(draft.gender),
        "race": draft.race,
        "diagnosis": diagnosis,
        "systolic_bp": reading.get("systolic"),
        "diastolic_bp": reading.get("diastolic"),
        "last_lab_date": draft.last_observation.date() if draft.last_observation else None,
        "diabetes_type2": DIABETES_TYPE2 in flags,
        "hypertension": HYPERTENSION in flags,
        "kidney_disease": KIDNEY_DISEASE in flags,
        "conditions": [
            {
                "display": fact.display,
                "system": fact.system,
                "code": fact.code,
                "onset": fact.onset.date().isoformat() if fact.onset else None,
                "active": fact.active,
            }
            for fact in draft.conditions
        ],
    }
