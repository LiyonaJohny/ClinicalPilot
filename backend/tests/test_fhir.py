import copy
import json
import unittest
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from pydantic import ValidationError

from support import SAMPLE_DATA

from app.fhir import BundleError, ingest_bundle
from app.main import app
from app.mapping import age_on, classify_code, parse_fhir_datetime
from app.persistence import IngestionReject, PatientRecord, session_scope
from app.schemas import Condition, Observation, Patient

BUNDLE = json.loads((SAMPLE_DATA / "fhir_bundle_synthea_style.json").read_text(encoding="utf-8"))
PATIENT_A = "8c1f0a52-0001-4b6e-9a11-000000000001"
PATIENT_B = "8c1f0a52-0002-4b6e-9a11-000000000002"
PATIENT_C = "8c1f0a52-0003-4b6e-9a11-000000000003"


def bundle_of(*resources: dict) -> dict:
    return {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": resource} for resource in resources]}


class FhirSchemaTest(unittest.TestCase):
    def test_patient_accepts_partial_birth_dates(self) -> None:
        patient = Patient.model_validate({"resourceType": "Patient", "id": "p1", "birthDate": "1970-05"})

        self.assertEqual(patient.birthDate, date(1970, 5, 1))

    def test_patient_rejects_bad_gender_and_missing_id(self) -> None:
        with self.assertRaises(ValidationError):
            Patient.model_validate({"resourceType": "Patient", "id": "p1", "birthDate": "1970-05-01", "gender": "banana"})
        with self.assertRaises(ValidationError):
            Patient.model_validate({"resourceType": "Patient", "birthDate": "1970-05-01"})

    def test_patient_rejects_implausible_birth_dates(self) -> None:
        for birth_date in ("2999-01-01", "1700-01-01", "not-a-date"):
            with self.subTest(birth_date=birth_date), self.assertRaises(ValidationError):
                Patient.model_validate({"resourceType": "Patient", "id": "p1", "birthDate": birth_date})

    def test_condition_requires_subject_and_code(self) -> None:
        with self.assertRaises(ValidationError):
            Condition.model_validate({"resourceType": "Condition", "subject": {"reference": "Patient/p1"}})
        with self.assertRaises(ValidationError):
            Condition.model_validate({"resourceType": "Condition", "code": {"text": "Hypertension"}})
        with self.assertRaises(ValidationError):
            Condition.model_validate({"resourceType": "Condition", "subject": {"reference": "Patient/p1"}, "code": {"coding": []}})

    def test_observation_requires_a_known_status(self) -> None:
        base = {"resourceType": "Observation", "subject": {"reference": "Patient/p1"}, "code": {"text": "BP"}}

        self.assertEqual(Observation.model_validate({**base, "status": "final"}).status, "final")
        with self.assertRaises(ValidationError):
            Observation.model_validate(base)
        with self.assertRaises(ValidationError):
            Observation.model_validate({**base, "status": "done"})


class ClinicalMappingTest(unittest.TestCase):
    def test_classify_code_maps_snomed_and_icd10(self) -> None:
        self.assertEqual(classify_code("snomed", "44054006"), "diabetes_type2")
        self.assertEqual(classify_code("snomed", "59621000"), "hypertension")
        self.assertEqual(classify_code("snomed", "433144002"), "kidney_disease")
        self.assertEqual(classify_code("icd10", "E11.9"), "diabetes_type2")
        self.assertEqual(classify_code("icd10", "i10"), "hypertension")
        self.assertEqual(classify_code("icd10", "N18.3"), "kidney_disease")

    def test_classify_code_ignores_other_codes(self) -> None:
        self.assertIsNone(classify_code("snomed", "15777000"))  # Prediabetes
        self.assertIsNone(classify_code("icd10", "E10.9"))  # Type 1 diabetes
        self.assertIsNone(classify_code("loinc", "44054006"))
        self.assertIsNone(classify_code(None, "44054006"))

    def test_age_on_counts_completed_years(self) -> None:
        self.assertEqual(age_on(date(1958, 3, 14), date(2024, 3, 13)), 65)
        self.assertEqual(age_on(date(1958, 3, 14), date(2024, 3, 14)), 66)

    def test_parse_fhir_datetime_normalizes_to_utc(self) -> None:
        self.assertEqual(parse_fhir_datetime("2024-03-01T22:30:00-05:00"), datetime(2024, 3, 2, 3, 30, tzinfo=UTC))
        self.assertEqual(parse_fhir_datetime("2024-01-05T14:20:00Z"), datetime(2024, 1, 5, 14, 20, tzinfo=UTC))
        self.assertEqual(parse_fhir_datetime("2024"), datetime(2024, 1, 1, tzinfo=UTC))
        self.assertIsNone(parse_fhir_datetime("yesterday"))


class FhirIngestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with session_scope() as session:
            cls.result = ingest_bundle(copy.deepcopy(BUNDLE), session)
        cls.patients = {patient["PatientID"]: patient for patient in cls.result.patients}

    def test_counts_valid_rejected_and_skipped_resources(self) -> None:
        self.assertEqual(self.result.patients_ingested, 3)
        self.assertEqual(self.result.conditions_mapped, 5)
        self.assertEqual(self.result.observations_mapped, 5)
        self.assertEqual(self.result.rejected_count, 7)
        self.assertEqual(self.result.skipped_resource_types, {"Claim": 1, "Encounter": 1})

    def test_maps_conditions_blood_pressure_and_demographics(self) -> None:
        patient = self.patients[PATIENT_A]

        self.assertEqual(patient["Source"], "fhir")
        self.assertEqual(patient["Gender"], "F")
        self.assertEqual(patient["Race"], "White")
        self.assertEqual(patient["Age"], age_on(date(1958, 3, 14), datetime.now(UTC).date()))
        self.assertEqual(patient["Diagnosis"], "Diabetes T2; Hypertension")
        self.assertTrue(patient["DiabetesType2"])
        self.assertTrue(patient["Hypertension"])
        self.assertFalse(patient["KidneyDisease"])

    def test_uses_the_most_recent_blood_pressure_panel(self) -> None:
        patient = self.patients[PATIENT_A]

        self.assertEqual((patient["SystolicBP"], patient["DiastolicBP"]), (146.0, 88.0))
        self.assertEqual(patient["LastLabDate"], "2024-03-01")

    def test_resolves_patient_slash_id_references_and_standalone_bp_observations(self) -> None:
        patient = self.patients[PATIENT_B]

        self.assertEqual(patient["Gender"], "M")
        self.assertEqual(patient["Race"], "Asian")
        self.assertEqual(patient["Diagnosis"], "Acute bronchitis (disorder)")
        self.assertEqual((patient["SystolicBP"], patient["DiastolicBP"]), (118.0, 76.0))
        self.assertFalse(patient["DiabetesType2"] or patient["Hypertension"] or patient["KidneyDisease"])

    def test_maps_icd10_kidney_disease_and_uses_age_at_death(self) -> None:
        patient = self.patients[PATIENT_C]

        self.assertTrue(patient["KidneyDisease"])
        self.assertEqual(patient["Diagnosis"], "Kidney Disease")
        self.assertEqual(patient["Age"], 77)
        self.assertIsNone(patient["SystolicBP"])
        self.assertIsNone(patient["Race"])

    def test_resolved_conditions_are_stored_but_not_active(self) -> None:
        with session_scope() as session:
            record = session.query(PatientRecord).filter(PatientRecord.patient_id == PATIENT_A).one()
            conditions = {condition["code"]: condition for condition in record.conditions}

        self.assertEqual(set(conditions), {"44054006", "59621000", "195662009"})
        self.assertFalse(conditions["195662009"]["active"])
        self.assertTrue(conditions["44054006"]["active"])
        self.assertEqual(conditions["44054006"]["onset"], "2009-06-20")

    def test_invalid_records_are_set_aside_with_a_reason(self) -> None:
        reasons = {rejected.resource_id: rejected for rejected in self.result.rejected}

        self.assertIn("birthDate: Field required", reasons["8c1f0a52-0004-4b6e-9a11-000000000004"].reason)
        self.assertIn("is in the future", reasons["8c1f0a52-0005-4b6e-9a11-000000000005"].reason)
        self.assertIn("does not match a valid Patient", reasons["5a000000-0000-4000-8000-000000000401"].reason)
        self.assertIn("code: Field required", reasons["5a000000-0000-4000-8000-000000000402"].reason)
        self.assertIn("status: Field required", reasons["5a000000-0000-4000-8000-000000000403"].reason)
        self.assertIn("implausible systolic blood pressure value 900", reasons["5a000000-0000-4000-8000-000000000404"].reason)
        self.assertIn("has no resource", reasons[None].reason)
        self.assertEqual(reasons[None].resource_type, "Unknown")

    def test_rejected_records_are_persisted_with_their_payload(self) -> None:
        with session_scope() as session:
            reject = session.query(IngestionReject).filter(IngestionReject.resource_id == "5a000000-0000-4000-8000-000000000404").first()

            self.assertIsNotNone(reject)
            self.assertEqual(reject.source, "fhir")
            self.assertEqual(reject.resource_type, "Observation")
            self.assertEqual(reject.payload["valueQuantity"]["value"], 900)

    def test_rejected_patients_are_not_stored(self) -> None:
        with session_scope() as session:
            stored = {record.patient_id for record in session.query(PatientRecord).all()}

        self.assertNotIn("8c1f0a52-0004-4b6e-9a11-000000000004", stored)
        self.assertNotIn("8c1f0a52-0005-4b6e-9a11-000000000005", stored)

    def test_reingesting_updates_instead_of_duplicating(self) -> None:
        updated = bundle_of(
            {"resourceType": "Patient", "id": PATIENT_B, "gender": "male", "birthDate": "1990-07-02"},
            {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{PATIENT_B}"},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "38341003", "display": "Hypertensive disorder"}]},
            },
        )
        try:
            with session_scope() as session:
                result = ingest_bundle(updated, session)
                count = session.query(PatientRecord).filter(PatientRecord.patient_id == PATIENT_B).count()

            self.assertEqual(count, 1)
            self.assertTrue(result.patients[0]["Hypertension"])
            self.assertEqual(result.patients[0]["Diagnosis"], "Hypertension")
        finally:
            with session_scope() as session:
                ingest_bundle(copy.deepcopy(BUNDLE), session)

    def test_duplicate_patient_ids_in_one_bundle_are_rejected(self) -> None:
        patient = {"resourceType": "Patient", "id": "dup-1", "birthDate": "1980-01-01"}
        with session_scope() as session:
            result = ingest_bundle(bundle_of(patient, dict(patient)), session)

        self.assertEqual(result.patients_ingested, 1)
        self.assertEqual(result.rejected[0].reason, "duplicate Patient id in bundle")

    def test_refuted_conditions_and_cancelled_observations_are_set_aside(self) -> None:
        bundle = bundle_of(
            {"resourceType": "Patient", "id": "ver-1", "birthDate": "1980-01-01"},
            {
                "resourceType": "Condition",
                "id": "c-refuted",
                "subject": {"reference": "Patient/ver-1"},
                "verificationStatus": {"coding": [{"code": "refuted"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006"}]},
            },
            {
                "resourceType": "Observation",
                "id": "o-cancelled",
                "status": "cancelled",
                "subject": {"reference": "Patient/ver-1"},
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                "valueQuantity": {"value": 150},
            },
        )
        with session_scope() as session:
            result = ingest_bundle(bundle, session)

        self.assertFalse(result.patients[0]["DiabetesType2"])
        self.assertIsNone(result.patients[0]["SystolicBP"])
        self.assertEqual({rejected.resource_id for rejected in result.rejected}, {"c-refuted", "o-cancelled"})

    def test_non_bundle_payload_raises(self) -> None:
        with session_scope() as session:
            with self.assertRaises(BundleError):
                ingest_bundle({"resourceType": "Patient", "id": "p1"}, session)


class FhirEndpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_ingest_fhir_endpoint_returns_summary_and_records_history(self) -> None:
        before = self.client.get("/storage/summary").json()

        response = self.client.post("/ingest/fhir", json=BUNDLE)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "fhir")
        self.assertEqual(payload["patients_ingested"], 3)
        self.assertEqual(payload["rejected_count"], 7)
        self.assertEqual(len(payload["rejected"]), 7)
        after = self.client.get("/storage/summary").json()
        self.assertEqual(after["ingestion_rejects"], before["ingestion_rejects"] + 7)
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_ingested_patients_are_listed(self) -> None:
        self.client.post("/ingest/fhir", json=BUNDLE)

        response = self.client.get("/patients", params={"limit": 500})

        self.assertEqual(response.status_code, 200)
        ids = {patient["PatientID"] for patient in response.json()["patients"]}
        self.assertTrue({PATIENT_A, PATIENT_B, PATIENT_C} <= ids)

    def test_ingest_fhir_endpoint_rejects_non_bundles_and_records_them(self) -> None:
        before = self.client.get("/storage/summary").json()

        response = self.client.post("/ingest/fhir", json={"resourceType": "Patient", "id": "p1"})

        self.assertEqual(response.status_code, 422)
        self.assertIn("Not a valid FHIR Bundle", response.json()["detail"])
        after = self.client.get("/storage/summary").json()
        self.assertEqual(after["ingestion_rejects"], before["ingestion_rejects"] + 1)
        self.assertEqual(after["patients"], before["patients"])


if __name__ == "__main__":
    unittest.main()
