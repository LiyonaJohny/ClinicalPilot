from typing import Any
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer


def profile_dataset(frame: pd.DataFrame) -> dict[str, Any]:
    total_rows = len(frame)
    missing = frame.isna().sum().to_dict()
    duplicate_count = int(frame["PatientID"].duplicated().sum()) if "PatientID" in frame.columns else int(frame.duplicated().sum())

    invalid_ages = 0
    if "Age" in frame.columns:
        invalid_ages = int(((frame["Age"] < 0) | (frame["Age"] > 120)).sum())

    numeric_columns = frame.select_dtypes(include=[np.number]).columns.tolist()
    outliers: dict[str, int] = {}
    if numeric_columns and len(frame) >= 5:
        imputed = SimpleImputer(strategy="median").fit_transform(frame[numeric_columns])
        labels = IsolationForest(contamination=0.08, random_state=42).fit_predict(imputed)
        for column in numeric_columns:
            outliers[column] = int((labels == -1).sum())

    return {
        "rows": total_rows,
        "columns": list(frame.columns),
        "missing_values": missing,
        "duplicate_records": duplicate_count,
        "invalid_ages": invalid_ages,
        "outliers": outliers,
        "quality_score": max(0, 100 - duplicate_count * 3 - invalid_ages * 5 - sum(int(v) for v in missing.values())),
        "recommended_actions": [
            "Review duplicate PatientID records",
            "Impute missing vital signs with median strategy",
            "Flag biologically implausible ages for source verification",
        ],
    }


def discover_cohort(filters: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    minimum_age = int(filters.get("minimum_age", 60))
    minimum_systolic = int(filters.get("minimum_systolic_bp", 140))
    cohort = frame[
        (frame["Age"] > minimum_age)
        & (frame["DiabetesType2"] == True)
        & (frame["SystolicBP"].fillna(0) >= minimum_systolic)
    ]
    return {
        "filters": filters,
        "matching_patients": int(cohort["PatientID"].nunique()),
        "population_share": round((cohort["PatientID"].nunique() / frame["PatientID"].nunique()) * 100, 2),
        "top_characteristics": ["Age > 60", "Type 2 Diabetes", "Systolic BP > 140"],
        "patients": cohort[["PatientID", "Age", "Gender", "Diagnosis", "SystolicBP", "DiastolicBP", "LastLabDate"]]
        .head(10)
        .to_dict(orient="records"),
    }


MAX_VALID_AGE = 120
TEXT_FILTERS = {
    "gender": "Gender",
    "race": "Race",
    "site": "Site",
    "treatment": "Treatment",
    "outcome": "Outcome",
}
FLAG_FILTERS = {
    "diabetes_type2": "DiabetesType2",
    "hypertension": "Hypertension",
    "kidney_disease": "KidneyDisease",
}
RANGE_FILTERS = {
    "min_age": ("Age", "min"),
    "max_age": ("Age", "max"),
    "min_systolic_bp": ("SystolicBP", "min"),
    "max_systolic_bp": ("SystolicBP", "max"),
    "min_diastolic_bp": ("DiastolicBP", "min"),
    "max_diastolic_bp": ("DiastolicBP", "max"),
}
GENDER_ALIASES = {"male": "m", "female": "f"}
PREVIEW_COLUMNS = ["PatientID", "Age", "Gender", "Diagnosis", "SystolicBP", "DiastolicBP", "Treatment", "Outcome", "Site"]


def unique_patients(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per PatientID, keeping the first occurrence."""
    if "PatientID" in frame.columns:
        return frame.drop_duplicates(subset=["PatientID"], keep="first")
    return frame.drop_duplicates()


def _require_column(frame: pd.DataFrame, column: str, used_by: str) -> None:
    if column not in frame.columns:
        raise ValueError(f"{used_by} needs column {column}, which this dataset does not have")


def filter_patients(filters: dict[str, Any], frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Apply optional cohort filters to unique patients. Returns the cohort and data-quality notes.

    Range filters are inclusive. A patient with a missing value never matches a range filter on that column.
    """
    patients = unique_patients(frame)
    mask = pd.Series(True, index=patients.index)
    notes: list[str] = []
    known = set(TEXT_FILTERS) | set(FLAG_FILTERS) | set(RANGE_FILTERS) | {"diagnosis_contains", "missing_bp", "exclude_invalid_age"}
    unknown = sorted(set(filters) - known)
    if unknown:
        raise ValueError(f"unknown filters: {', '.join(unknown)}")

    for name, column in TEXT_FILTERS.items():
        wanted = filters.get(name)
        if wanted is None:
            continue
        _require_column(patients, column, name)
        wanted = str(wanted).strip().lower()
        if name == "gender":
            wanted = GENDER_ALIASES.get(wanted, wanted)
        mask &= patients[column].astype("string").str.strip().str.lower().eq(wanted).fillna(False)
    for name, column in FLAG_FILTERS.items():
        wanted = filters.get(name)
        if wanted is None:
            continue
        _require_column(patients, column, name)
        mask &= patients[column].astype(bool) == bool(wanted)
    for name, (column, bound) in RANGE_FILTERS.items():
        wanted = filters.get(name)
        if wanted is None:
            continue
        _require_column(patients, column, name)
        values = pd.to_numeric(patients[column], errors="coerce")
        mask &= (values >= float(wanted)) if bound == "min" else (values <= float(wanted))
        missing = int(values.isna().sum())
        if missing and column != "Age":
            note = f"{missing} patients have no {column} value and cannot match a {column} filter"
            if note not in notes:
                notes.append(note)
    if filters.get("diagnosis_contains") is not None:
        _require_column(patients, "Diagnosis", "diagnosis_contains")
        needle = str(filters["diagnosis_contains"]).strip().lower()
        mask &= patients["Diagnosis"].astype("string").str.lower().str.contains(needle, regex=False).fillna(False)
    if filters.get("missing_bp") is not None:
        _require_column(patients, "SystolicBP", "missing_bp")
        missing_bp = patients["SystolicBP"].isna()
        if "DiastolicBP" in patients.columns:
            missing_bp |= patients["DiastolicBP"].isna()
        mask &= missing_bp == bool(filters["missing_bp"])
    if "Age" in patients.columns:
        ages = pd.to_numeric(patients["Age"], errors="coerce")
        invalid_age = (ages < 0) | (ages > MAX_VALID_AGE)
        if filters.get("exclude_invalid_age"):
            mask &= ~invalid_age
        elif int((mask & invalid_age).sum()):
            notes.append(
                f"{int((mask & invalid_age).sum())} matching patients have an implausible age (outside 0-{MAX_VALID_AGE}); "
                "set exclude_invalid_age to leave them out"
            )
    return patients[mask], notes


def query_cohort(filters: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    """Count the unique patients matching optional filters. With no filters it counts everyone."""
    filters = {key: value for key, value in filters.items() if value is not None}
    cohort, notes = filter_patients(filters, frame)
    total = len(unique_patients(frame))
    preview = [column for column in PREVIEW_COLUMNS if column in cohort.columns]
    patients = cohort[preview].head(10).astype(object).where(cohort[preview].head(10).notna(), None)
    return {
        "filters": filters,
        "matching_patients": int(len(cohort)),
        "total_patients": int(total),
        "population_share": round(len(cohort) / total * 100, 2) if total else 0.0,
        "patient_ids": cohort["PatientID"].astype(str).head(50).tolist() if "PatientID" in cohort.columns else [],
        "patients": patients.to_dict(orient="records"),
        "notes": notes,
    }


def _number(value: Any) -> float | None:
    return None if pd.isna(value) else round(float(value), 2)


def _numeric_summary(values: pd.Series) -> dict[str, Any]:
    present = values.dropna()
    return {
        "count": int(present.count()),
        "missing": int(values.isna().sum()),
        "mean": _number(present.mean()) if len(present) else None,
        "median": _number(present.median()) if len(present) else None,
        "min": _number(present.min()) if len(present) else None,
        "max": _number(present.max()) if len(present) else None,
        "std": _number(present.std()) if len(present) > 1 else None,
    }


def dataset_stats(column: str | None, frame: pd.DataFrame, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summary statistics over unique patients, for one column or for the whole dataset.

    Pass filters (same keys as query_cohort) to compute the statistics within a cohort.
    """
    filters = {key: value for key, value in (filters or {}).items() if value is not None}
    patients, notes = filter_patients(filters, frame)
    basis = "unique patients (duplicate PatientID rows removed)"
    if column is None or column.strip() in ("", "*"):
        everyone = unique_patients(frame)
        ages = pd.to_numeric(everyone["Age"], errors="coerce") if "Age" in everyone.columns else pd.Series(dtype=float)
        return {
            "column": None,
            "basis": basis,
            "filters": filters,
            "rows": int(len(frame)),
            "unique_patients": int(len(everyone)),
            "duplicate_rows": int(len(frame) - len(everyone)),
            "patients_in_scope": int(len(patients)),
            "columns": list(frame.columns),
            "invalid_ages": int(((ages < 0) | (ages > MAX_VALID_AGE)).sum()),
            "missing_values": {name: int(count) for name, count in everyone.isna().sum().items() if int(count)},
            "notes": notes,
        }

    lookup = {name.lower(): name for name in frame.columns}
    name = lookup.get(column.strip().lower())
    if name is None:
        raise ValueError(f"unknown column {column!r}; available columns: {', '.join(frame.columns)}")
    values = patients[name]
    result: dict[str, Any] = {"column": name, "basis": basis, "filters": filters, "patients_in_scope": int(len(patients)), "notes": notes}
    if pd.api.types.is_bool_dtype(values):
        true_count = int(values.sum())
        result.update(
            kind="boolean",
            true_count=true_count,
            false_count=int(len(values) - true_count),
            true_percent=round(true_count / len(values) * 100, 2) if len(values) else 0.0,
        )
    elif pd.api.types.is_numeric_dtype(values):
        result.update(kind="numeric", **_numeric_summary(values))
        if name == "Age":
            valid = values[(values >= 0) & (values <= MAX_VALID_AGE)]
            result["invalid_values"] = int(values.notna().sum() - len(valid))
            result["valid_only"] = _numeric_summary(valid)
            if result["invalid_values"]:
                result["notes"] = [*notes, f"{result['invalid_values']} implausible ages are included in the top-level statistics and excluded from valid_only"]
        if values.notna().any() and "PatientID" in patients.columns:
            result["max_patient_ids"] = patients.loc[values == values.max(), "PatientID"].astype(str).tolist()
            result["min_patient_ids"] = patients.loc[values == values.min(), "PatientID"].astype(str).tolist()
    else:
        text = values.astype("string")
        counts = text.value_counts(dropna=True)
        result.update(
            kind="categorical",
            distinct=int(counts.size),
            missing=int(text.isna().sum()),
            value_counts={str(key): int(count) for key, count in counts.head(25).items()},
        )
        if name == "Diagnosis":
            terms = text.dropna().str.split(";").explode().str.strip()
            result["term_counts"] = {str(key): int(count) for key, count in terms[terms != ""].value_counts().items()}
    return result


def evaluate_protocol(criteria: str, frame: pd.DataFrame) -> dict[str, Any]:
    eligible = frame[
        (frame["Age"].between(18, 65))
        & (frame["DiabetesType2"] == True)
        & (frame["KidneyDisease"] == False)
    ]
    return {
        "criteria": criteria,
        "eligible_patients": int(eligible["PatientID"].nunique()),
        "ineligible_patients": int(frame["PatientID"].nunique() - eligible["PatientID"].nunique()),
        "major_exclusion_reasons": ["eGFR < 30", "Age outside 18-65", "Incomplete diabetes history"],
    }
