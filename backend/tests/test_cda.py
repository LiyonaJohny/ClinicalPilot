import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from lxml import etree

from support import SAMPLE_DATA

from app import cda
from app.cda import CdaError, ingest_document, parse_document
from app.main import app
from app.mapping import age_on, parse_hl7_timestamp
from app.persistence import IngestionReject, PatientRecord, session_scope

DOCUMENT = (SAMPLE_DATA / "ccda_synthea_style.xml").read_bytes()
PATIENT_ID = "c0da0000-0000-4000-8000-0000000000a1"


def minimal_document(patient_role: str) -> bytes:
    return f'<ClinicalDocument xmlns="urn:hl7-org:v3"><recordTarget>{patient_role}</recordTarget></ClinicalDocument>'.encode()


class Hl7TimestampTest(unittest.TestCase):
    def test_parses_all_precisions(self) -> None:
        self.assertEqual(parse_hl7_timestamp("1962"), datetime(1962, 1, 1, tzinfo=UTC))
        self.assertEqual(parse_hl7_timestamp("196208"), datetime(1962, 8, 1, tzinfo=UTC))
        self.assertEqual(parse_hl7_timestamp("19620818"), datetime(1962, 8, 18, tzinfo=UTC))
        self.assertEqual(parse_hl7_timestamp("20240305101500"), datetime(2024, 3, 5, 10, 15, tzinfo=UTC))

    def test_applies_utc_offsets(self) -> None:
        self.assertEqual(parse_hl7_timestamp("20240305101500-0500"), datetime(2024, 3, 5, 15, 15, tzinfo=UTC))
        self.assertEqual(parse_hl7_timestamp("20240305101500.000+0100"), datetime(2024, 3, 5, 9, 15, tzinfo=UTC))

    def test_rejects_malformed_values(self) -> None:
        for value in (None, "", "pending", "2024-03-05", "20241340", "202403051"):
            with self.subTest(value=value):
                self.assertIsNone(parse_hl7_timestamp(value))


class CdaIngestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with session_scope() as session:
            cls.result = ingest_document(DOCUMENT, session)
        cls.patient = cls.result.patients[0]

    def test_maps_demographics_into_the_patient_model(self) -> None:
        self.assertEqual(self.result.source, "cda")
        self.assertEqual(self.result.patients_ingested, 1)
        self.assertEqual(self.patient["PatientID"], PATIENT_ID)
        self.assertEqual(self.patient["Source"], "cda")
        self.assertEqual(self.patient["Gender"], "F")
        self.assertEqual(self.patient["Race"], "Black or African American")
        self.assertEqual(self.patient["Age"], age_on(date(1962, 8, 18), datetime.now(UTC).date()))

    def test_maps_problems_including_icd10_translations(self) -> None:
        self.assertEqual(self.result.conditions_mapped, 3)
        self.assertEqual(self.patient["Diagnosis"], "Diabetes T2; Hypertension")
        self.assertTrue(self.patient["DiabetesType2"])
        self.assertTrue(self.patient["Hypertension"])
        self.assertFalse(self.patient["KidneyDisease"])

    def test_nested_status_observations_are_not_treated_as_problems(self) -> None:
        with session_scope() as session:
            record = session.query(PatientRecord).filter(PatientRecord.patient_id == PATIENT_ID).one()
            conditions = {condition["code"]: condition for condition in record.conditions}

        self.assertEqual(set(conditions), {"44054006", "I10", "195662009"})
        self.assertFalse(conditions["195662009"]["active"])
        self.assertEqual(conditions["I10"]["onset"], "2004-02-09")

    def test_uses_the_most_recent_valid_blood_pressure(self) -> None:
        self.assertEqual(self.result.observations_mapped, 6)
        self.assertEqual((self.patient["SystolicBP"], self.patient["DiastolicBP"]), (144.0, 90.0))
        self.assertEqual(self.patient["LastLabDate"], "2024-04-12")

    def test_invalid_entries_are_set_aside_with_a_reason(self) -> None:
        reasons = sorted(rejected.reason for rejected in self.result.rejected)

        self.assertEqual(self.result.rejected_count, 2)
        self.assertEqual(reasons, ["blood pressure value 'pending' is not numeric", "problem observation value has no code"])
        with session_scope() as session:
            stored = session.query(IngestionReject).filter(IngestionReject.source == "cda", IngestionReject.resource_type == "Problem").first()
            self.assertIn("nullFlavor", stored.payload)

    def test_reingesting_does_not_duplicate_the_patient(self) -> None:
        with session_scope() as session:
            ingest_document(DOCUMENT, session)
            count = session.query(PatientRecord).filter(PatientRecord.patient_id == PATIENT_ID).count()

        self.assertEqual(count, 1)


class CdaValidationTest(unittest.TestCase):
    def assert_rejected(self, data: bytes, expected: str) -> None:
        with self.assertRaises(CdaError) as raised:
            parse_document(data)
        self.assertIn(expected, str(raised.exception))

    def test_rejects_malformed_xml(self) -> None:
        self.assert_rejected(b"<ClinicalDocument", "not well-formed XML")

    def test_rejects_other_root_elements(self) -> None:
        self.assert_rejected(b'<Bundle xmlns="http://hl7.org/fhir"/>', "not an HL7 v3 ClinicalDocument")

    def test_rejects_missing_patient_role(self) -> None:
        self.assert_rejected(b'<ClinicalDocument xmlns="urn:hl7-org:v3"/>', "patientRole is missing")

    def test_rejects_missing_patient_id(self) -> None:
        self.assert_rejected(minimal_document("<patientRole><patient/></patientRole>"), "no id")

    def test_rejects_missing_or_invalid_birth_time(self) -> None:
        self.assert_rejected(minimal_document('<patientRole><id extension="p1"/><patient/></patientRole>'), "birthTime is missing or not a valid")
        self.assert_rejected(
            minimal_document('<patientRole><id extension="p1"/><patient><birthTime value="29990101"/></patient></patientRole>'),
            "in the future",
        )

    def test_minimal_valid_document_has_no_conditions_or_vitals(self) -> None:
        draft, rejects, problems, observations = parse_document(
            minimal_document('<patientRole><id extension="p1"/><patient><birthTime value="19800101"/></patient></patientRole>')
        )

        self.assertEqual(draft.patient_id, "p1")
        self.assertEqual((rejects, problems, observations), ([], 0, 0))

    def test_external_entities_are_not_expanded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "secret.txt"
            secret.write_text("TOP-SECRET-CONTENT", encoding="utf-8")
            document = (
                f'<?xml version="1.0"?><!DOCTYPE ClinicalDocument [<!ENTITY secret SYSTEM "{secret.as_uri()}">]>'
                '<ClinicalDocument xmlns="urn:hl7-org:v3"><title>&secret;</title><recordTarget><patientRole>'
                '<id extension="safe-id"/><patient><birthTime value="19800101"/></patient></patientRole></recordTarget></ClinicalDocument>'
            ).encode()

            root = etree.fromstring(document, cda._parser())
            draft, _, _, _ = parse_document(document)

        self.assertNotIn("TOP-SECRET-CONTENT", etree.tostring(root, encoding="unicode", method="text"))
        self.assertEqual(draft.patient_id, "safe-id")


class CdaEndpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_ingest_cda_endpoint_accepts_an_uploaded_document(self) -> None:
        before = self.client.get("/storage/summary").json()

        response = self.client.post("/ingest/cda", files={"file": ("patient.xml", DOCUMENT, "application/xml")})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["patients"][0]["PatientID"], PATIENT_ID)
        self.assertEqual(payload["conditions_mapped"], 3)
        self.assertEqual(payload["rejected_count"], 2)
        after = self.client.get("/storage/summary").json()
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)
        self.assertEqual(after["ingestion_rejects"], before["ingestion_rejects"] + 2)

    def test_ingest_cda_endpoint_rejects_invalid_documents_and_records_them(self) -> None:
        before = self.client.get("/storage/summary").json()

        response = self.client.post("/ingest/cda", files={"file": ("broken.xml", b"<not-cda/>", "application/xml")})

        self.assertEqual(response.status_code, 422)
        self.assertIn("Not a valid C-CDA document", response.json()["detail"])
        after = self.client.get("/storage/summary").json()
        self.assertEqual(after["ingestion_rejects"], before["ingestion_rejects"] + 1)
        self.assertEqual(after["patients"], before["patients"])


if __name__ == "__main__":
    unittest.main()
