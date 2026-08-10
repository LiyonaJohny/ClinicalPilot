import unittest
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.quality import discover_cohort, evaluate_protocol, profile_dataset


class QualityEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            [
                {
                    "PatientID": "CP-1",
                    "Age": 64,
                    "Gender": "F",
                    "Diagnosis": "Diabetes T2; Hypertension",
                    "SystolicBP": 150,
                    "DiastolicBP": 92,
                    "LastLabDate": "2024-01-01",
                    "DiabetesType2": True,
                    "Hypertension": True,
                    "KidneyDisease": False,
                },
                {
                    "PatientID": "CP-1",
                    "Age": 64,
                    "Gender": "F",
                    "Diagnosis": "Diabetes T2; Hypertension",
                    "SystolicBP": 150,
                    "DiastolicBP": 92,
                    "LastLabDate": "2024-01-01",
                    "DiabetesType2": True,
                    "Hypertension": True,
                    "KidneyDisease": False,
                },
                {
                    "PatientID": "CP-2",
                    "Age": 250,
                    "Gender": "M",
                    "Diagnosis": "N/A",
                    "SystolicBP": None,
                    "DiastolicBP": None,
                    "LastLabDate": "2024-01-02",
                    "DiabetesType2": False,
                    "Hypertension": False,
                    "KidneyDisease": True,
                },
            ],
        )

    def test_profile_dataset_reports_quality_defects(self) -> None:
        profile = profile_dataset(self.frame)

        self.assertEqual(profile["rows"], 3)
        self.assertEqual(profile["duplicate_records"], 1)
        self.assertEqual(profile["invalid_ages"], 1)
        self.assertEqual(profile["missing_values"]["SystolicBP"], 1)
        self.assertIn("Review duplicate PatientID records", profile["recommended_actions"])

    def test_discover_cohort_applies_age_diabetes_and_blood_pressure_filters(self) -> None:
        cohort = discover_cohort({"minimum_age": 60, "minimum_systolic_bp": 140}, self.frame)

        self.assertEqual(cohort["matching_patients"], 1)
        self.assertEqual(cohort["population_share"], 50.0)
        self.assertEqual(cohort["patients"][0]["PatientID"], "CP-1")

    def test_evaluate_protocol_counts_eligible_and_ineligible_patients(self) -> None:
        result = evaluate_protocol("Adults 18-65 with diabetes and no kidney disease", self.frame)

        self.assertEqual(result["eligible_patients"], 1)
        self.assertEqual(result["ineligible_patients"], 1)
        self.assertIn("Age outside 18-65", result["major_exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
