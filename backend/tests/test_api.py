import unittest
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


class ApiEndpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "clinicalpilot-ai"})

    def test_list_datasets_returns_sample_dataset_metadata(self) -> None:
        response = self.client.get("/datasets")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["datasets"][0]["name"], "Cardiovascular_Phase_II.csv")
        self.assertEqual(payload["datasets"][0]["rows"], 18)
        self.assertIn("PatientID", payload["datasets"][0]["columns"])

    def test_demo_profile_returns_quality_summary(self) -> None:
        response = self.client.get("/datasets/demo-profile")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows"], 18)
        self.assertEqual(payload["duplicate_records"], 1)
        self.assertEqual(payload["invalid_ages"], 1)

    def test_dataset_profile_accepts_csv_upload(self) -> None:
        csv_body = (
            "PatientID,Age,Gender,Diagnosis,SystolicBP,DiastolicBP,"
            "LastLabDate,DiabetesType2,Hypertension,KidneyDisease\n"
            "CP-1,64,F,Diabetes T2,150,92,2024-01-01,true,true,false\n"
            "CP-1,64,F,Diabetes T2,150,92,2024-01-01,true,true,false\n"
            "CP-2,250,M,N/A,,,2024-01-02,false,false,true\n"
        )

        response = self.client.post(
            "/datasets/profile",
            files={"file": ("patients.csv", csv_body, "text/csv")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows"], 3)
        self.assertEqual(payload["duplicate_records"], 1)
        self.assertEqual(payload["invalid_ages"], 1)

    def test_cohort_discovery_endpoint(self) -> None:
        response = self.client.post(
            "/cohorts/discover",
            json={"minimum_age": 60, "minimum_systolic_bp": 140},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["matching_patients"], 1)
        self.assertIn("Age > 60", payload["top_characteristics"])

    def test_protocol_check_endpoint(self) -> None:
        response = self.client.post(
            "/protocols/check",
            json={"criteria": "Adults aged 18-65 with Type 2 Diabetes"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["criteria"], "Adults aged 18-65 with Type 2 Diabetes")
        self.assertEqual(payload["eligible_patients"], 4)
        self.assertEqual(payload["ineligible_patients"], 13)

    def test_paper_analysis_endpoint_accepts_upload(self) -> None:
        response = self.client.post(
            "/papers/analyze",
            files={"file": ("study.txt", "Clinical trial paper text", "text/plain")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filename"], "study.txt")
        self.assertIn("study_objective", payload)
        self.assertIn("limitations", payload)

    def test_chat_endpoint_returns_dataset_answer_and_sources(self) -> None:
        response = self.client.post(
            "/chat",
            json={"question": "What percent of diabetic patients also have hypertension?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["question"], "What percent of diabetic patients also have hypertension?")
        self.assertEqual(payload["answer"], "44% of diabetic patients also have hypertension in the packaged cardiovascular dataset.")
        self.assertIn("Cardiovascular_Phase_II.csv", payload["sources"])


if __name__ == "__main__":
    unittest.main()
