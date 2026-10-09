import unittest
from unittest import mock

from fastapi.testclient import TestClient

from support import FakeClient, FakeEmbedder, message, text_block, tool_use_block

from app import llm, rag
from app.main import app


class ApiEndpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def storage_summary(self) -> dict[str, int]:
        response = self.client.get("/storage/summary")
        self.assertEqual(response.status_code, 200)
        return response.json()

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
        before = self.storage_summary()
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
        after = self.storage_summary()
        self.assertEqual(after["datasets"], before["datasets"] + 1)
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_cohort_discovery_endpoint(self) -> None:
        before = self.storage_summary()
        response = self.client.post(
            "/cohorts/discover",
            json={"minimum_age": 60, "minimum_systolic_bp": 140},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["matching_patients"], 1)
        self.assertIn("Age > 60", payload["top_characteristics"])
        after = self.storage_summary()
        self.assertEqual(after["cohorts"], before["cohorts"] + 1)
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_protocol_check_endpoint(self) -> None:
        before = self.storage_summary()
        response = self.client.post(
            "/protocols/check",
            json={"criteria": "Adults aged 18-65 with Type 2 Diabetes"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["criteria"], "Adults aged 18-65 with Type 2 Diabetes")
        self.assertEqual(payload["eligible_patients"], 4)
        self.assertEqual(payload["ineligible_patients"], 13)
        after = self.storage_summary()
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_paper_analysis_endpoint_accepts_upload(self) -> None:
        before = self.storage_summary()
        summary = rag.PaperSummary(
            study_objective="Objective",
            population="Population",
            methods="Methods",
            results="Results",
            limitations="Limitations",
            cited_excerpts=[1],
        )
        with (
            mock.patch.object(rag, "get_embedder", return_value=FakeEmbedder()),
            mock.patch.object(llm, "get_client", return_value=FakeClient([message([], parsed_output=summary)])),
        ):
            response = self.client.post(
                "/papers/analyze",
                files={"file": ("study.txt", "Clinical trial paper text", "text/plain")},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filename"], "study.txt")
        self.assertEqual(payload["study_objective"], "Objective")
        self.assertEqual(payload["limitations"], "Limitations")
        self.assertEqual(payload["sources"][0]["excerpt"], "Clinical trial paper text")
        after = self.storage_summary()
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_chat_endpoint_returns_dataset_answer_and_sources(self) -> None:
        before = self.storage_summary()
        fake_llm = FakeClient(
            [
                message(
                    [tool_use_block("toolu_1", "dataset_stats", {"column": "Hypertension", "filters": {"diabetes_type2": True}})],
                    stop_reason="tool_use",
                ),
                message([text_block("44% of diabetic patients also have hypertension (4 of 9).")]),
            ]
        )
        with mock.patch.object(llm, "get_client", return_value=fake_llm):
            response = self.client.post(
                "/chat",
                json={"question": "What percent of diabetic patients also have hypertension?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["question"], "What percent of diabetic patients also have hypertension?")
        self.assertEqual(payload["answer"], "44% of diabetic patients also have hypertension (4 of 9).")
        self.assertIn("Cardiovascular_Phase_II.csv", payload["sources"])
        after = self.storage_summary()
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_generated_report_endpoint_persists_report_and_history(self) -> None:
        before = self.storage_summary()

        response = self.client.post(
            "/reports",
            json={
                "title": "Q3 Hypertension Report",
                "dataset_name": "Cardiovascular_Phase_II.csv",
                "content": "Report body",
                "metadata": {"quality_score": 86},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "saved")
        self.assertGreater(payload["id"], 0)
        after = self.storage_summary()
        self.assertEqual(after["generated_reports"], before["generated_reports"] + 1)
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_storage_summary_reports_all_persistent_record_types(self) -> None:
        payload = self.storage_summary()

        self.assertEqual(
            set(payload),
            {"datasets", "generated_reports", "cohorts", "analysis_history", "patients", "ingestion_rejects", "papers", "paper_chunks"},
        )


if __name__ == "__main__":
    unittest.main()
