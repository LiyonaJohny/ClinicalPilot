import io
import unittest
import zipfile
from unittest import mock

from fastapi.testclient import TestClient

from support import FakeClient, FakeEmbedder, message, text_block

from app import llm, rag
from app.main import app
from app.persistence import PaperChunk, pgvector_search_statement, session_scope
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

PAPER = """Objective. This randomized trial evaluated whether Compound-X lowers systolic blood pressure in adults with type 2 diabetes and hypertension.

Population. We enrolled 412 adults aged 40 to 75 across four sites. Patients with an eGFR below 30 were excluded from enrollment.

Methods. Participants were randomized one to one to Compound-X or standard care and followed for 24 weeks. The primary endpoint was the change in seated systolic blood pressure.

Results. Compound-X reduced systolic blood pressure by 11.2 mmHg compared with 4.1 mmHg under standard care. Serious adverse events were similar between arms.

Limitations. Adults older than 75 and patients with severe renal impairment were under-represented, and follow-up was limited to 24 weeks.
"""

SUMMARY = rag.PaperSummary(
    study_objective="Tests whether Compound-X lowers systolic blood pressure.",
    population="412 adults aged 40 to 75.",
    methods="Randomized one to one, 24 weeks of follow-up.",
    results="Systolic blood pressure fell by 11.2 mmHg on Compound-X.",
    limitations="Older adults were under-represented.",
    cited_excerpts=[1, 1, 99],
)


class RagTestCase(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(rag, "get_embedder", return_value=FakeEmbedder())
        patcher.start()
        self.addCleanup(patcher.stop)


class ChunkingTest(unittest.TestCase):
    def test_short_text_is_one_chunk(self) -> None:
        self.assertEqual(rag.chunk_text("Clinical trial paper text"), ["Clinical trial paper text"])

    def test_long_text_is_split_with_overlap_and_nothing_is_lost(self) -> None:
        sentences = [f"Sentence number {index} describes finding {index}." for index in range(120)]
        text = " ".join(sentences)

        chunks = rag.chunk_text(text, size=300, overlap=60)

        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(chunk) <= 300 for chunk in chunks))
        for sentence in sentences:
            self.assertTrue(any(sentence in chunk for chunk in chunks), sentence)
        for first, second in zip(chunks, chunks[1:]):
            self.assertIn(second[:20], first)

    def test_chunks_prefer_sentence_boundaries(self) -> None:
        text = " ".join(f"Sentence number {index} describes finding {index}." for index in range(40))

        chunks = rag.chunk_text(text, size=300, overlap=60)

        self.assertTrue(all(chunk.endswith(".") for chunk in chunks))

    def test_chunks_start_at_word_boundaries(self) -> None:
        words = [f"word{index}" for index in range(400)]

        chunks = rag.chunk_text(" ".join(words), size=200, overlap=50)

        self.assertGreater(len(chunks), 10)
        for chunk in chunks:
            self.assertTrue(set(chunk.split()) <= set(words), chunk)

    def test_overlap_must_be_smaller_than_size(self) -> None:
        with self.assertRaises(ValueError):
            rag.chunk_text("text", size=100, overlap=100)


class ExtractTextTest(unittest.TestCase):
    def test_reads_plain_text(self) -> None:
        self.assertEqual(rag.extract_text("study.txt", b"  Plain text body  "), "Plain text body")

    def test_reads_docx_paragraphs(self) -> None:
        namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        document = f'<w:document xmlns:w="{namespace}"><w:body><w:p><w:r><w:t>First </w:t></w:r><w:r><w:t>paragraph.</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p></w:body></w:document>'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document)

        self.assertEqual(rag.extract_text("study.docx", buffer.getvalue()), "First paragraph.\n\nSecond paragraph.")

    def test_rejects_unsupported_and_empty_files(self) -> None:
        with self.assertRaises(rag.UnsupportedDocument):
            rag.extract_text("study.doc", b"binary")
        with self.assertRaises(rag.UnsupportedDocument):
            rag.extract_text("study.txt", b"   ")
        with self.assertRaises(rag.UnsupportedDocument):
            rag.extract_text("study.docx", b"not a zip archive")


class PgvectorSqlTest(unittest.TestCase):
    """The PostgreSQL path is checked at the SQL level, since tests run on SQLite."""

    def test_embedding_column_is_a_pgvector_column_on_postgresql_and_json_on_sqlite(self) -> None:
        table = PaperChunk.__table__

        self.assertIn("embedding VECTOR(384) NOT NULL", str(CreateTable(table).compile(dialect=postgresql.dialect())))
        self.assertIn("embedding JSON NOT NULL", str(CreateTable(table).compile(dialect=sqlite.dialect())))

    def test_search_orders_by_cosine_distance_with_a_limit(self) -> None:
        statement = pgvector_search_statement([0.0] * 384, top_k=5, paper_id=7)

        sql = str(statement.compile(dialect=postgresql.dialect()))

        self.assertIn("paper_chunks.embedding <=> ", sql)
        self.assertIn("ORDER BY paper_chunks.embedding <=> ", sql)
        self.assertIn("WHERE paper_chunks.paper_id = ", sql)
        self.assertIn("LIMIT ", sql)


class RetrievalTest(RagTestCase):
    def test_index_paper_stores_one_embedding_per_chunk(self) -> None:
        with session_scope() as session:
            paper = rag.index_paper(session, "indexed.txt", PAPER)
            chunks = session.query(PaperChunk).filter(PaperChunk.paper_id == paper.id).order_by(PaperChunk.chunk_index).all()

            self.assertEqual(paper.chunk_count, len(chunks))
            self.assertEqual([chunk.chunk_index for chunk in chunks], list(range(len(chunks))))
            self.assertTrue(all(len(chunk.embedding) == 384 for chunk in chunks))

    def test_search_returns_the_most_similar_chunks_first(self) -> None:
        with session_scope() as session:
            paper = rag.index_paper(session, "ranking.txt", "\n\n".join(paragraph * 4 for paragraph in PAPER.split("\n\n")))
            results = rag.search_papers(session, "severe renal impairment under-represented older adults limitations", top_k=3, paper_id=paper.id)

        self.assertEqual(len(results), 3)
        self.assertIn("under-represented", results[0]["content"])
        self.assertEqual([result["score"] for result in results], sorted((result["score"] for result in results), reverse=True))
        self.assertEqual(results[0]["paper"], "ranking.txt")

    def test_search_can_be_limited_to_one_paper(self) -> None:
        with session_scope() as session:
            first = rag.index_paper(session, "first.txt", "Aspirin reduced cardiovascular events in the treatment arm.")
            rag.index_paper(session, "second.txt", "Aspirin reduced cardiovascular events in the treatment arm.")
            results = rag.search_papers(session, "aspirin cardiovascular events", top_k=10, paper_id=first.id)

        self.assertEqual({result["paper"] for result in results}, {"first.txt"})

    def test_summary_is_built_only_from_retrieved_chunks_and_returns_sources(self) -> None:
        client = FakeClient([message([], parsed_output=SUMMARY)])
        with session_scope() as session:
            paper = rag.index_paper(session, "summary.txt", PAPER)
            result = rag.summarize_paper(session, paper, client)
            stored = [chunk.content for chunk in session.query(PaperChunk).filter(PaperChunk.paper_id == paper.id)]

        call = client.messages.calls[0]
        prompt = call["messages"][0]["content"]
        self.assertIs(call["output_format"], rag.PaperSummary)
        self.assertIn("Use only the numbered excerpts", call["system"])
        self.assertIn("[1] (chunk 0)", prompt)
        for content in stored:
            self.assertIn(content, prompt)
        self.assertEqual(result["results"], SUMMARY.results)
        # Excerpt 1 was cited twice and 99 does not exist, so exactly one source comes back.
        self.assertEqual([source["chunk_index"] for source in result["sources"]], [0])
        self.assertEqual(result["sources"][0]["paper"], "summary.txt")

    def test_summary_falls_back_to_all_retrieved_chunks_when_none_are_cited(self) -> None:
        uncited = SUMMARY.model_copy(update={"cited_excerpts": []})
        client = FakeClient([message([], parsed_output=uncited)])
        with session_scope() as session:
            paper = rag.index_paper(session, "uncited.txt", PAPER)
            result = rag.summarize_paper(session, paper, client)

        self.assertEqual(len(result["sources"]), paper.chunk_count)

    def test_summary_raises_when_the_model_refuses_or_returns_nothing(self) -> None:
        for response in (message([], stop_reason="refusal"), message([], stop_reason="max_tokens")):
            with self.subTest(stop_reason=response.stop_reason), session_scope() as session:
                paper = rag.index_paper(session, "failed.txt", PAPER)
                with self.assertRaises(llm.LLMError):
                    rag.summarize_paper(session, paper, FakeClient([response]))


class PaperEndpointTest(RagTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_analyze_endpoint_indexes_summarizes_and_returns_sources(self) -> None:
        before = self.client.get("/storage/summary").json()

        with mock.patch.object(llm, "get_client", return_value=FakeClient([message([], parsed_output=SUMMARY)])):
            response = self.client.post("/papers/analyze", files={"file": ("study.txt", PAPER, "text/plain")})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filename"], "study.txt")
        self.assertEqual(payload["study_objective"], SUMMARY.study_objective)
        self.assertEqual(payload["limitations"], SUMMARY.limitations)
        self.assertGreaterEqual(payload["chunks_indexed"], 1)
        self.assertEqual(payload["sources"][0]["paper"], "study.txt")
        after = self.client.get("/storage/summary").json()
        self.assertEqual(after["papers"], before["papers"] + 1)
        self.assertEqual(after["paper_chunks"], before["paper_chunks"] + payload["chunks_indexed"])
        self.assertEqual(after["analysis_history"], before["analysis_history"] + 1)

    def test_analyze_endpoint_returns_503_and_stores_nothing_without_credentials(self) -> None:
        before = self.client.get("/storage/summary").json()

        with mock.patch.object(llm, "get_client", side_effect=llm.LLMNotConfigured("No Anthropic credentials found.")):
            response = self.client.post("/papers/analyze", files={"file": ("study.txt", PAPER, "text/plain")})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get("/storage/summary").json(), before)

    def test_analyze_endpoint_rolls_back_the_index_when_the_summary_fails(self) -> None:
        before = self.client.get("/storage/summary").json()

        with mock.patch.object(llm, "get_client", return_value=FakeClient([message([], stop_reason="refusal")])):
            response = self.client.post("/papers/analyze", files={"file": ("study.txt", PAPER, "text/plain")})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get("/storage/summary").json(), before)

    def test_analyze_endpoint_rejects_unsupported_files(self) -> None:
        response = self.client.post("/papers/analyze", files={"file": ("study.doc", b"binary", "application/msword")})

        self.assertEqual(response.status_code, 415)

    def test_search_endpoint_returns_ranked_excerpts(self) -> None:
        with session_scope() as session:
            rag.index_paper(session, "searchable.txt", PAPER)

        response = self.client.get("/papers/search", params={"query": "primary endpoint systolic blood pressure", "top_k": 2})

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 2)
        self.assertIn("excerpt", results[0])


if __name__ == "__main__":
    unittest.main()
