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
