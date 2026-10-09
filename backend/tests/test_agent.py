import json
import unittest
from unittest import mock

import pandas as pd
from fastapi.testclient import TestClient
from pydantic import ValidationError

from support import SAMPLE_DATA, FakeClient, FakeEmbedder, message, text_block, tool_use_block

from app import agent, llm, rag
from app.fhir import ingest_bundle
from app.main import app
from app.persistence import session_scope
from app.quality import dataset_stats, query_cohort

FRAME = pd.read_csv(SAMPLE_DATA / "cardiovascular_phase_ii.csv")
QUESTION = "What percent of diabetic patients also have hypertension?"


def scripted_overlap_client() -> FakeClient:
    """A model that calls discover_cohort twice in parallel, then answers from the results."""
    return FakeClient(
        [
            message(
                [
                    text_block("Checking the cohort."),
                    tool_use_block("toolu_1", "discover_cohort", {"filters": {"diabetes_type2": True}}),
                    tool_use_block("toolu_2", "discover_cohort", {"filters": {"diabetes_type2": True, "hypertension": True}}),
                ],
                stop_reason="tool_use",
            ),
            message([text_block("44% of diabetic patients also have hypertension (4 of 9 unique patients).")]),
        ]
    )


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


class CohortToolTest(unittest.TestCase):
    def test_counts_unique_patients_not_rows(self) -> None:
        result = query_cohort({}, FRAME)

        self.assertEqual(len(FRAME), 18)
        self.assertEqual(result["matching_patients"], 17)
        self.assertEqual(result["total_patients"], 17)
        self.assertEqual(result["population_share"], 100.0)

    def test_filters_combine_with_and(self) -> None:
        result = query_cohort({"diabetes_type2": True, "hypertension": True}, FRAME)

        self.assertEqual(result["matching_patients"], 4)
        self.assertEqual(sorted(result["patient_ids"]), ["CP-10012", "CP-10014", "CP-10017", "CP-88421"])
        self.assertEqual(result["population_share"], 23.53)

    def test_range_filters_are_inclusive_and_skip_missing_values(self) -> None:
        result = query_cohort({"min_systolic_bp": 140}, FRAME)

        self.assertEqual(result["matching_patients"], 9)
        self.assertIn("3 patients have no SystolicBP value and cannot match a SystolicBP filter", result["notes"])

    def test_text_filters_ignore_case_and_accept_gender_words(self) -> None:
        self.assertEqual(query_cohort({"gender": "female"}, FRAME)["matching_patients"], 9)
        self.assertEqual(query_cohort({"site": "nyc-01"}, FRAME)["matching_patients"], 7)
        self.assertEqual(query_cohort({"treatment": "compound-x", "outcome": "Controlled"}, FRAME)["matching_patients"], 9)
        self.assertEqual(query_cohort({"diagnosis_contains": "kidney"}, FRAME)["matching_patients"], 1)

    def test_implausible_ages_are_flagged_and_can_be_excluded(self) -> None:
        flagged = query_cohort({"min_age": 61}, FRAME)
        clean = query_cohort({"min_age": 61, "exclude_invalid_age": True}, FRAME)

        self.assertEqual(flagged["matching_patients"], 9)
        self.assertTrue(any("implausible age" in note for note in flagged["notes"]))
        self.assertEqual(clean["matching_patients"], 8)
        self.assertEqual(clean["notes"], [])

    def test_missing_bp_filter(self) -> None:
        self.assertEqual(sorted(query_cohort({"missing_bp": True}, FRAME)["patient_ids"]), ["CP-10012", "CP-10018", "CP-9903"])
        self.assertEqual(query_cohort({"missing_bp": False}, FRAME)["matching_patients"], 14)

    def test_unknown_filters_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            query_cohort({"minimum_age": 60}, FRAME)

    def test_result_is_json_serializable(self) -> None:
        json.dumps(query_cohort({"missing_bp": True}, FRAME))
        json.dumps(dataset_stats(None, FRAME))
        json.dumps(dataset_stats("Age", FRAME))
        json.dumps(dataset_stats("Diagnosis", FRAME))
        json.dumps(dataset_stats("Hypertension", FRAME))


class DatasetStatsToolTest(unittest.TestCase):
    def test_overview_reports_rows_duplicates_and_missing_values(self) -> None:
        result = dataset_stats(None, FRAME)

        self.assertEqual(result["rows"], 18)
        self.assertEqual(result["unique_patients"], 17)
        self.assertEqual(result["duplicate_rows"], 1)
        self.assertEqual(result["invalid_ages"], 1)
        self.assertEqual(result["missing_values"]["SystolicBP"], 3)

    def test_numeric_column_statistics(self) -> None:
        result = dataset_stats("systolicbp", FRAME)

        self.assertEqual(result["column"], "SystolicBP")
        self.assertEqual(result["kind"], "numeric")
        self.assertEqual((result["count"], result["missing"]), (14, 3))
        self.assertEqual((result["min"], result["max"]), (90.0, 170.0))
        self.assertEqual(result["max_patient_ids"], ["CP-10017"])

    def test_age_statistics_separate_implausible_values(self) -> None:
        result = dataset_stats("Age", FRAME)

        self.assertEqual(result["max"], 250.0)
        self.assertEqual(result["invalid_values"], 1)
        self.assertEqual(result["valid_only"]["count"], 16)
        self.assertEqual(result["valid_only"]["mean"], 59.31)
        self.assertEqual(result["valid_only"]["max"], 81.0)

    def test_boolean_and_categorical_columns(self) -> None:
        diabetes = dataset_stats("DiabetesType2", FRAME)
        outcome = dataset_stats("Outcome", FRAME)
        diagnosis = dataset_stats("Diagnosis", FRAME)

        self.assertEqual((diabetes["true_count"], diabetes["false_count"]), (9, 8))
        self.assertEqual(outcome["value_counts"], {"Controlled": 12, "Uncontrolled": 3, "Readmitted": 2})
        self.assertEqual(diagnosis["term_counts"]["Diabetes T2"], 9)

    def test_statistics_within_a_cohort(self) -> None:
        result = dataset_stats("Hypertension", FRAME, {"diabetes_type2": True})

        self.assertEqual(result["patients_in_scope"], 9)
        self.assertEqual(result["true_count"], 4)
        self.assertEqual(result["true_percent"], 44.44)

    def test_unknown_column_lists_the_available_ones(self) -> None:
        with self.assertRaises(ValueError) as raised:
            dataset_stats("Cholesterol", FRAME)
        self.assertIn("SystolicBP", str(raised.exception))


class ExecuteToolTest(unittest.TestCase):
    def test_discover_cohort_cites_the_sample_dataset(self) -> None:
        result, sources = agent.execute_tool("discover_cohort", {"filters": {"kidney_disease": True}})

        self.assertEqual(result["matching_patients"], 1)
        self.assertEqual(sources, ["Cardiovascular_Phase_II.csv"])

    def test_dataset_stats_accepts_no_arguments(self) -> None:
        result, _ = agent.execute_tool("dataset_stats", {})

        self.assertEqual(result["unique_patients"], 17)

    def test_invalid_inputs_raise_validation_errors(self) -> None:
        for name, tool_input in (
            ("discover_cohort", {"filters": {"minimum_age": 60}}),
            ("discover_cohort", {"filters": {}, "dataset": "production"}),
            ("dataset_stats", {"column": 5}),
            ("search_papers", {"query": ""}),
            ("search_papers", {"query": "x", "top_k": 50}),
            ("discover_cohort", "not an object"),
        ):
            with self.subTest(name=name, tool_input=tool_input), self.assertRaises(ValidationError):
                agent.execute_tool(name, tool_input)

    def test_unknown_tool_raises(self) -> None:
        with self.assertRaises(ValueError):
            agent.execute_tool("delete_everything", {})

    def test_ingested_dataset_uses_patients_loaded_through_fhir(self) -> None:
        bundle = json.loads((SAMPLE_DATA / "fhir_bundle_synthea_style.json").read_text(encoding="utf-8"))
        with session_scope() as session:
            ingest_bundle(bundle, session)

        result, sources = agent.execute_tool("discover_cohort", {"filters": {"kidney_disease": True}, "dataset": "ingested"})

        self.assertIn("8c1f0a52-0003-4b6e-9a11-000000000003", result["patient_ids"])
        self.assertEqual(sources, ["Ingested patients (FHIR and CDA)"])

    def test_search_papers_returns_excerpts_and_chunk_sources(self) -> None:
        with mock.patch.object(rag, "get_embedder", return_value=FakeEmbedder()):
            with session_scope() as session:
                rag.index_paper(session, "agent_paper.txt", "Zolpidem trial reported improved sleep latency in the treatment arm.")
            result, sources = agent.execute_tool("search_papers", {"query": "zolpidem sleep latency", "top_k": 1})

        self.assertEqual(result["results"][0]["paper"], "agent_paper.txt")
        self.assertIn("Zolpidem", result["results"][0]["text"])
        self.assertEqual(sources, ["agent_paper.txt (chunk 0)"])


class AgentLoopTest(unittest.TestCase):
    def test_tool_definitions_match_the_validators(self) -> None:
        self.assertEqual([tool["name"] for tool in agent.TOOLS], ["discover_cohort", "dataset_stats", "search_papers"])
        self.assertEqual(set(agent.COHORT_FILTER_PROPERTIES), set(agent.CohortFilters.model_fields))

    def test_runs_tools_and_returns_a_grounded_answer(self) -> None:
        client = scripted_overlap_client()

        result = agent.answer_question(QUESTION, client)

        self.assertEqual(result["question"], QUESTION)
        self.assertEqual(result["answer"], "44% of diabetic patients also have hypertension (4 of 9 unique patients).")
        self.assertEqual(result["sources"], ["Cardiovascular_Phase_II.csv"])
        self.assertEqual([call["name"] for call in result["tool_calls"]], ["discover_cohort", "discover_cohort"])
        self.assertFalse(any(call["is_error"] for call in result["tool_calls"]))

    def test_sends_tools_system_prompt_and_model_settings(self) -> None:
        client = scripted_overlap_client()

        agent.answer_question(QUESTION, client)

        first = client.messages.calls[0]
        self.assertEqual(first["model"], llm.MODEL)
        self.assertEqual(first["tools"], agent.TOOLS)
        self.assertEqual(first["system"], agent.SYSTEM_PROMPT)
        self.assertEqual(first["messages"], [{"role": "user", "content": QUESTION}])
        self.assertEqual(first["output_config"], {"effort": llm.EFFORT})

    def test_returns_all_parallel_tool_results_in_one_user_message(self) -> None:
        client = scripted_overlap_client()

        agent.answer_question(QUESTION, client)

        second = client.messages.calls[1]["messages"]
        self.assertEqual([turn["role"] for turn in second], ["user", "assistant", "user"])
        results = second[2]["content"]
        self.assertEqual([item["tool_use_id"] for item in results], ["toolu_1", "toolu_2"])
        self.assertEqual(json.loads(results[0]["content"])["matching_patients"], 9)
        self.assertEqual(json.loads(results[1]["content"])["matching_patients"], 4)

    def test_event_stream_order(self) -> None:
        events = list(agent.run_agent(QUESTION, scripted_overlap_client()))

        kinds = [event["type"] for event in events]
        self.assertEqual(kinds[:3], ["token", "token", "token"])
        self.assertEqual(kinds[3:7], ["tool_call", "tool_result", "tool_call", "tool_result"])
        self.assertEqual(kinds[-1], "done")
        self.assertTrue(all(kind == "token" for kind in kinds[7:-1]))
        streamed = "".join(event["text"] for event in events[7:-1])
        self.assertEqual(streamed.strip(), events[-1]["answer"])

    def test_tool_errors_are_reported_back_to_the_model(self) -> None:
        client = FakeClient(
            [
                message([tool_use_block("toolu_1", "discover_cohort", {"filters": {"minimum_age": 60}})], stop_reason="tool_use"),
                message([tool_use_block("toolu_2", "discover_cohort", {"filters": {"min_age": 61, "exclude_invalid_age": True}})], stop_reason="tool_use"),
                message([text_block("8 patients are older than 60.")]),
            ]
        )

        result = agent.answer_question("How many patients are older than 60?", client)

        error_result = client.messages.calls[1]["messages"][2]["content"][0]
        self.assertTrue(error_result["is_error"])
        self.assertIn("minimum_age", error_result["content"])
        self.assertEqual([call["is_error"] for call in result["tool_calls"]], [True, False])
        self.assertEqual(result["answer"], "8 patients are older than 60.")

    def test_answer_without_tools_has_no_sources(self) -> None:
        result = agent.answer_question("Hello", FakeClient([message([text_block("Hello. Ask me about the dataset.")])]))

        self.assertEqual(result["sources"], [])
        self.assertEqual(result["tool_calls"], [])

    def test_refusals_truncation_and_empty_answers_raise(self) -> None:
        cases = {
            "refusal": message([], stop_reason="refusal"),
            "truncated answer": message([text_block("The answer is")], stop_reason="max_tokens"),
            "truncated tool call": message([tool_use_block("toolu_1", "dataset_stats", {})], stop_reason="max_tokens"),
            "empty answer": message([]),
        }
        for label, response in cases.items():
            with self.subTest(label), self.assertRaises(llm.LLMError):
                agent.answer_question("Question", FakeClient([response]))

    def test_truncated_tool_calls_are_never_executed(self) -> None:
        executor = mock.Mock()
        client = FakeClient([message([tool_use_block("toolu_1", "dataset_stats", {})], stop_reason="max_tokens")])

        with self.assertRaises(llm.LLMError):
            list(agent.run_agent("Question", client, tool_executor=executor))

        executor.assert_not_called()

    def test_stops_after_the_turn_limit(self) -> None:
        looping = [message([tool_use_block(f"toolu_{index}", "dataset_stats", {})], stop_reason="tool_use") for index in range(3)]

        with self.assertRaises(llm.LLMError):
            list(agent.run_agent("Question", FakeClient(looping), max_turns=3))


class ChatEndpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def history_count(self) -> int:
        return self.client.get("/storage/summary").json()["analysis_history"]

    def test_chat_returns_the_answer_sources_and_tool_calls(self) -> None:
        before = self.history_count()

        with mock.patch.object(llm, "get_client", return_value=scripted_overlap_client()):
            response = self.client.post("/chat", json={"question": QUESTION})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["question"], QUESTION)
        self.assertIn("44%", payload["answer"])
        self.assertEqual(payload["sources"], ["Cardiovascular_Phase_II.csv"])
        self.assertEqual(len(payload["tool_calls"]), 2)
        self.assertEqual(self.history_count(), before + 1)

    def test_chat_stream_emits_server_sent_events(self) -> None:
        before = self.history_count()

        with mock.patch.object(llm, "get_client", return_value=scripted_overlap_client()):
            response = self.client.post("/chat/stream", json={"question": QUESTION})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = parse_sse(response.text)
        kinds = [kind for kind, _ in events]
        self.assertEqual(kinds[-1], "done")
        self.assertEqual(kinds.count("tool_call"), 2)
        self.assertEqual(kinds.count("tool_result"), 2)
        self.assertGreater(kinds.count("token"), 3)
        done = events[-1][1]
        self.assertEqual(done["answer"], "44% of diabetic patients also have hypertension (4 of 9 unique patients).")
        self.assertEqual(done["sources"], ["Cardiovascular_Phase_II.csv"])
        tokens_after_tools = "".join(data["text"] for kind, data in events[kinds.index("tool_result") :] if kind == "token")
        self.assertEqual(tokens_after_tools.strip(), done["answer"])
        self.assertEqual(self.history_count(), before + 1)

    def test_chat_stream_reports_model_failures_as_an_error_event(self) -> None:
        with mock.patch.object(llm, "get_client", return_value=FakeClient([message([], stop_reason="refusal")])):
            response = self.client.post("/chat/stream", json={"question": QUESTION})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse_sse(response.text), [("error", {"detail": "The model declined to answer this question."})])

    def test_chat_endpoints_return_503_without_credentials(self) -> None:
        before = self.history_count()

        with mock.patch.object(llm, "get_client", side_effect=llm.LLMNotConfigured("No Anthropic credentials found.")):
            chat = self.client.post("/chat", json={"question": QUESTION})
            stream = self.client.post("/chat/stream", json={"question": QUESTION})

        self.assertEqual(chat.status_code, 503)
        self.assertEqual(stream.status_code, 503)
        self.assertIn("No Anthropic credentials", chat.json()["detail"])
        self.assertEqual(self.history_count(), before)

    def test_chat_endpoints_require_a_question(self) -> None:
        for path in ("/chat", "/chat/stream"):
            for payload in ({}, {"question": "   "}, {"question": 5}):
                with self.subTest(path=path, payload=payload):
                    self.assertEqual(self.client.post(path, json=payload).status_code, 422)

    def test_chat_reports_model_failures_as_502(self) -> None:
        with mock.patch.object(llm, "get_client", return_value=FakeClient([message([], stop_reason="refusal")])):
            response = self.client.post("/chat", json={"question": QUESTION})

        self.assertEqual(response.status_code, 502)


class LlmConfigurationTest(unittest.TestCase):
    def test_get_client_raises_when_no_credentials_are_available(self) -> None:
        bare = mock.Mock(api_key=None, auth_token=None, credentials=None)
        with mock.patch.object(llm.anthropic, "Anthropic", return_value=bare):
            with self.assertRaises(llm.LLMNotConfigured):
                llm.get_client()

    def test_get_client_returns_a_client_with_an_api_key(self) -> None:
        configured = mock.Mock(api_key="test-key", auth_token=None, credentials=None)
        with mock.patch.object(llm.anthropic, "Anthropic", return_value=configured):
            self.assertIs(llm.get_client(), configured)

    def test_refusal_fallback_is_opt_in(self) -> None:
        with mock.patch.dict("os.environ", {"CLINICALPILOT_REFUSAL_FALLBACK": ""}):
            self.assertNotIn("extra_body", llm.request_options())
        with mock.patch.dict("os.environ", {"CLINICALPILOT_REFUSAL_FALLBACK": "1"}):
            options = llm.request_options()
        self.assertEqual(options["extra_body"], {"fallbacks": "default"})
        self.assertEqual(options["extra_headers"], {"anthropic-beta": "server-side-fallback-2026-07-01"})


if __name__ == "__main__":
    unittest.main()
