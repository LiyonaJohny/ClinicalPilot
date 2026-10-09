import importlib.util
import unittest

import pandas as pd

from support import BACKEND_DIR, SAMPLE_DATA, FakeClient, message, text_block, tool_use_block

from app import agent, llm

spec = importlib.util.spec_from_file_location("run_evals", BACKEND_DIR / "evals" / "run_evals.py")
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)

ITEMS = run_evals.load_golden()
NUMBER_ITEM = {"id": "n", "question": "?", "answer_type": "number", "expected": 44, "tolerance": 0.5}
TEXT_ITEM = {"id": "t", "question": "?", "answer_type": "text", "expected": "CP-10017"}


class GoldenFileTest(unittest.TestCase):
    def test_has_twenty_distinct_questions(self) -> None:
        self.assertEqual(len(ITEMS), 20)
        self.assertEqual(len({item["id"] for item in ITEMS}), 20)
        self.assertEqual(len({item["question"] for item in ITEMS}), 20)

    def test_expected_answers_match_the_tools(self) -> None:
        self.assertEqual(run_evals.check_golden(ITEMS), [])

    def test_expected_answers_match_an_independent_pandas_calculation(self) -> None:
        frame = pd.read_csv(SAMPLE_DATA / "cardiovascular_phase_ii.csv")
        unique = frame.drop_duplicates("PatientID")
        valid = unique[unique["Age"].between(0, 120)]
        diabetic = unique[unique["DiabetesType2"]]
        independent = {
            "q01": len(unique),
            "q02": len(frame) - len(unique),
            "q03": len(diabetic),
            "q04": int(unique["Hypertension"].sum()),
            "q05": int(unique["KidneyDisease"].sum()),
            "q06": int(diabetic["Hypertension"].sum()),
            "q07": round(diabetic["Hypertension"].mean() * 100),
            "q08": int(unique["SystolicBP"].isna().sum()),
            "q09": int((unique["SystolicBP"] >= 140).sum()),
            "q10": unique["SystolicBP"].max(),
            "q11": unique.loc[unique["SystolicBP"].idxmax(), "PatientID"],
            "q12": int((unique["Treatment"] == "Compound-X").sum()),
            "q13": int(((unique["Treatment"] == "Standard Care") & (unique["Outcome"] == "Controlled")).sum()),
            "q14": int((unique["Outcome"] == "Readmitted").sum()),
            "q15": int((unique["Site"] == "NYC-01").sum()),
            "q16": int((unique["Gender"] == "F").sum()),
            "q17": len(unique) - len(valid),
            "q18": round(valid["Age"].mean(), 1),
            "q19": int((valid["DiabetesType2"] & (valid["Age"] > 60) & (valid["SystolicBP"] >= 140)).sum()),
            "q20": unique["SystolicBP"].median(),
        }

        for item in ITEMS:
            with self.subTest(item["id"]):
                self.assertEqual(independent[item["id"]], item["expected"])


class ScoringTest(unittest.TestCase):
    def test_reads_the_value_from_the_last_answer_line(self) -> None:
        self.assertEqual(run_evals.final_answer("Working.\nANSWER: 3\nActually.\nanswer: 44%"), "44%")
        self.assertIsNone(run_evals.final_answer("The answer is 44."))

    def test_number_answers(self) -> None:
        self.assertTrue(run_evals.score_answer(NUMBER_ITEM, "4 of 9 diabetic patients.\nANSWER: 44%")[0])
        self.assertTrue(run_evals.score_answer(NUMBER_ITEM, "ANSWER: 44.4")[0])
        self.assertFalse(run_evals.score_answer(NUMBER_ITEM, "ANSWER: 45")[0])
        self.assertFalse(run_evals.score_answer(NUMBER_ITEM, "ANSWER: about half")[0])
        self.assertTrue(run_evals.score_answer({**NUMBER_ITEM, "expected": 1200, "tolerance": 0}, "ANSWER: 1,200")[0])

    def test_a_number_elsewhere_in_the_text_does_not_count(self) -> None:
        correct, detail = run_evals.score_answer(NUMBER_ITEM, "44% of diabetic patients also have hypertension.")

        self.assertFalse(correct)
        self.assertEqual(detail, "no ANSWER line")

    def test_text_answers(self) -> None:
        self.assertTrue(run_evals.score_answer(TEXT_ITEM, "ANSWER: cp-10017")[0])
        self.assertFalse(run_evals.score_answer(TEXT_ITEM, "ANSWER: CP-10014")[0])

    def test_grounded_needs_a_successful_tool_call_and_a_source(self) -> None:
        call = {"name": "discover_cohort", "input": {}, "is_error": False}

        self.assertTrue(run_evals.is_grounded({"tool_calls": [call], "sources": ["Cardiovascular_Phase_II.csv"]}))
        self.assertFalse(run_evals.is_grounded({"tool_calls": [], "sources": []}))
        self.assertFalse(run_evals.is_grounded({"tool_calls": [{**call, "is_error": True}], "sources": []}))


class EvaluateTest(unittest.TestCase):
    def test_scores_grounded_ungrounded_and_failed_answers(self) -> None:
        items = ITEMS[:3]
        client = FakeClient(
            [
                message([tool_use_block("toolu_1", "dataset_stats", {})], stop_reason="tool_use"),
                message([text_block("There are 17 unique patients.\nANSWER: 17")]),
                message([text_block("Probably one.\nANSWER: 1")]),
                message([], stop_reason="refusal"),
            ]
        )

        summary = run_evals.evaluate(items, lambda question: agent.answer_question(question, client))

        self.assertEqual((summary["total"], summary["correct"], summary["grounded"], summary["correct_and_grounded"]), (3, 2, 1, 1))
        self.assertEqual([entry["grounded"] for entry in summary["items"]], [True, False, False])
        self.assertTrue(summary["items"][2]["detail"].startswith("error:"))
        self.assertTrue(client.messages.calls[0]["messages"][0]["content"].endswith(run_evals.ANSWER_INSTRUCTION))

    def test_main_reports_missing_credentials(self) -> None:
        from unittest import mock

        with (
            mock.patch.object(llm, "get_client", side_effect=llm.LLMNotConfigured("No Anthropic credentials found.")),
            mock.patch("sys.argv", ["run_evals.py"]),
        ):
            self.assertEqual(run_evals.main(), 2)


if __name__ == "__main__":
    unittest.main()
