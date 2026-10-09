# ClinicalPilot AI - Project Report

Status date: August 10, 2026

## 1. Executive Summary

ClinicalPilot AI is a clinical research web application for dataset quality review, cohort discovery, clinical paper insight extraction, study report generation, and digital twin-style operational simulation.

The project currently contains a working React + TypeScript frontend, a FastAPI backend scaffold, sample cardiovascular clinical data, Docker configuration, and a production build pipeline. The frontend now has typed API-client integration for dataset upload/profiling, cohort discovery, protocol checks, paper analysis, and dataset chat, with local fallback feedback when the backend is unavailable.

The application is running locally at:

```text
http://127.0.0.1:5173
```

## 2. Current Technology Stack

- Frontend: React 18, TypeScript, Vite, Material UI, Recharts, TanStack React Query
- Backend: FastAPI, Pandas, NumPy, Scikit-Learn, python-multipart, HTTPX, SQLAlchemy, psycopg
- Optional AI/RAG dependencies: OpenAI, LangChain, ChromaDB in `backend/requirements-ai.txt`
- Deployment assets: Dockerfile for frontend, backend Dockerfile, Docker Compose with PostgreSQL
- Dataset: `sample_data/cardiovascular_phase_ii.csv`

## 3. Repository Structure

- `src/App.tsx`: Main application UI and interactive workflows
- `src/api.ts`: Typed frontend client for the FastAPI backend endpoints
- `src/activityRouting.ts`: Recent activity navigation targets and feedback messages
- `src/clinicalData.ts`: Packaged clinical demo records and computed analytics
- `src/data.ts`: Navigation types, activity items, and paper insight demo content
- `src/navigation.ts`: Shared desktop/mobile navigation configuration
- `src/tableUtils.ts`: Shared search, sort, and pagination helpers for data tables
- `src/theme.ts`: Material UI theme
- `src/styles.css`: Global styles
- `backend/app/main.py`: FastAPI app and API endpoints
- `backend/app/persistence.py`: SQLAlchemy persistence models and save helpers for datasets, reports, cohorts, and analysis history
- `backend/app/quality.py`: Dataset profiling, cohort discovery, and protocol evaluation logic
- `backend/requirements.txt`: Core backend runtime and test dependencies
- `backend/requirements-ai.txt`: Optional AI/RAG dependencies separated from core runtime
- `backend/tests/test_api.py`: FastAPI endpoint tests
- `backend/tests/test_quality.py`: Dataset quality engine tests
- `sample_data/cardiovascular_phase_ii.csv`: Demo cardiovascular clinical dataset
- `docker-compose.yml`: Frontend, API, and PostgreSQL service configuration
- `README.md`: Existing setup and feature overview
- `tests/api.test.ts`: Mocked frontend/API contract tests

## 4. Work Already Done

### Frontend Application

- Built a full clinical research dashboard with sidebar navigation.
- Added dashboard metrics for total patients, average age, data quality score, disease distribution, enrollment trends, missing data, and recent activity.
- Added dataset quality review UI with invalid-entry, missing-value, duplicate-ID, patient preview table, and health map sections.
- Added paper analyzer UI with upload area, document preview, and AI insight extraction cards.
- Added cohort discovery UI with age, comorbidity, systolic BP filters, cohort analysis summary, and protocol eligibility panel.
- Added study report generator UI with report configuration, generated draft preview, chart, and AI summary.
- Added digital twin simulator UI for enrollment, capacity, staffing, projected staffing need, completion date, and capacity risk.
- Added Material UI theme and polished layout styling.

### Functionality Enabled in This Pass

- Dataset upload buttons now open a file picker and stage selected files locally.
- Dataset upload now posts files to `POST /datasets/profile` and displays returned profile metrics.
- Paper upload area now opens a file picker, posts files to `POST /papers/analyze`, and refreshes insight cards from the API response.
- Dataset table filter toggles between all rows and data-quality issue rows.
- Patient and cohort tables now support full-column search, sortable headers, and pagination.
- Dataset preview exports to CSV.
- Cohort export generates a CSV.
- Responsive mobile navigation is enabled with a top-bar menu button and slide-out drawer.
- Recent activities now navigate to their related app sections.
- Study report export generates a text report.
- Header, sidebar, notification, AI assistant, and settings controls now show useful local feedback.
- Cohort filters are controlled and call `POST /cohorts/discover`.
- Protocol analysis calls `POST /protocols/check` and displays API eligibility results.
- Report title, report type, and AI insight toggle are editable.
- AI assistant accepts questions through `POST /chat` and falls back to local clinical-data answers when the API is unavailable.
- Simulator sliders are controlled and recalculate staffing, completion, and capacity risk after running a scenario.

### Backend/API

Implemented FastAPI endpoints:

- `GET /health`: API health check
- `GET /datasets`: Lists packaged sample dataset metadata
- `POST /datasets/profile`: Profiles uploaded CSV/XLS/XLSX data
- `GET /datasets/demo-profile`: Profiles packaged demo dataset
- `POST /cohorts/discover`: Discovers matching cohort records
- `POST /protocols/check`: Evaluates protocol criteria against sample data
- `POST /papers/analyze`: Returns structured paper-analysis fields for uploaded documents
- `POST /chat`: Answers a dataset question using packaged sample data
- `POST /reports`: Persists generated report content and metadata
- `GET /storage/summary`: Reports persisted record counts for datasets, reports, cohorts, and analysis history

Implemented backend data-quality logic:

- Missing-value counts
- Duplicate PatientID detection
- Invalid age detection
- Numeric outlier estimation with IsolationForest
- Quality score calculation
- Recommended cleaning actions
- Cohort filtering
- Protocol eligibility calculation
- Chat percentage calculation now uses unique `PatientID` records to match frontend analytics.

Completed backend setup and local API verification:

- Created `.venv` using the bundled Python runtime.
- Installed core backend dependencies from `backend/requirements.txt`.
- Started FastAPI locally with Uvicorn at `http://127.0.0.1:8000`.
- Verified all implemented API routes over HTTP.
- Added backend test suite with 11 passing tests.
- Moved ChromaDB/LangChain/OpenAI into `backend/requirements-ai.txt` because ChromaDB's native `chroma-hnswlib` dependency requires Microsoft C++ Build Tools on this machine and is not used by the current API routes.

Implemented persistence:

- Added SQLAlchemy models for uploaded dataset profiles, generated reports, cohort discovery results, and analysis history.
- Docker/production persistence uses PostgreSQL through `DATABASE_URL`; the existing Docker Compose file provides `postgresql://clinicalpilot:clinicalpilot@db:5432/clinicalpilot`.
- The backend normalizes PostgreSQL URLs to the psycopg SQLAlchemy driver.
- Standalone local runs without `DATABASE_URL` use a local SQLite database file so the API remains runnable on machines without Docker.
- Backend tests use isolated SQLite databases through the same SQLAlchemy persistence code path.
- Dataset profile uploads persist a dataset record and analysis-history record.
- Cohort discovery persists a cohort record and analysis-history record.
- Protocol checks, paper analysis, and chat persist analysis-history records.
- Generated reports persist report content, metadata, and analysis-history records.
- Live local API verification created 1 dataset record, 1 generated report, 1 cohort record, and 6 analysis-history records.

Implemented frontend/API integration:

- `profileDataset`: posts uploaded CSV/XLS/XLSX files to `/datasets/profile`
- `analyzePaper`: posts uploaded paper files to `/papers/analyze`
- `discoverCohort`: posts cohort filters to `/cohorts/discover`
- `checkProtocol`: posts criteria text to `/protocols/check`
- `chatWithDataset`: posts dataset questions to `/chat`
- Default API base URL is `http://127.0.0.1:8000` and can be overridden with `VITE_API_BASE_URL`

## 5. Current Verification

Completed checks:

```text
npm test
npm run backend:test
npm exec tsc -- --noEmit
npm run build
Invoke-WebRequest http://127.0.0.1:5173
HTTP checks against http://127.0.0.1:8000
```

Results:

- Node test suite passed with 29 tests.
- Backend Python test suite passed with 13 tests.
- TypeScript check passed.
- Production Vite build passed.
- Local frontend server returned HTTP 200.
- Local frontend is running at `http://127.0.0.1:5173`.
- Local FastAPI server is running at `http://127.0.0.1:8000`.
- Verified `GET /health`, `GET /datasets`, `GET /datasets/demo-profile`, `POST /datasets/profile`, `POST /cohorts/discover`, `POST /protocols/check`, `POST /papers/analyze`, `POST /chat`, `POST /reports`, and `GET /storage/summary`.

Notes:

- Vite needed to run outside the Codex sandbox because the sandbox blocked Vite/esbuild from loading `vite.config.ts`.
- Python is still not installed as a normal system command in this environment, so backend commands use `.venv\Scripts\python.exe`.
- Optional AI/RAG dependencies were not installed because ChromaDB needs native Windows build tools; the current backend API does not require those packages.
- Docker is not installed on this machine, so PostgreSQL container verification could not be run locally; PostgreSQL is wired through Docker Compose and `DATABASE_URL`.
- A Playwright visual smoke test was attempted but blocked by a local permission error accessing the Codex app data directory.

## 6. What Is Yet To Be Done

### Production Frontend Integration

- Replace local-only snackbar feedback with persisted workflow states.
- Add loading, success, empty, and error states for every API-backed operation.
- Add user-facing validation for unsupported upload formats and malformed files.

### Backend Completion

- Add stronger validation with Pydantic request/response models.
- Add safer handling for missing columns and invalid uploaded files.
- Implement real document/PDF parsing for paper analysis.
- Implement real OpenAI/LangChain/ChromaDB RAG flows or remove unused dependencies if not planned.

### Security, Compliance, and Clinical Readiness

- Add authentication and role-based access control.
- Add audit logging for uploads, report generation, and data exports.
- Add PHI/PII handling rules, de-identification controls, and compliance documentation.
- Add data retention, deletion, and export governance.
- Add model-output disclaimers and clinical review workflows.
- Add source citations for AI-generated answers and report sections.

### DevOps and Quality

- Add frontend unit/component tests.
- Add backend unit/API tests.
- Add end-to-end tests for the main user journeys.
- Add CI workflow for lint, build, and tests.
- Verify Docker Compose end-to-end startup for frontend, API, and PostgreSQL.
- Add environment variable documentation.
- Add production deployment instructions.

## 7. Recommended Next Milestones

1. API schema hardening: add Pydantic request/response models and invalid-file/missing-column handling.
2. API state hardening: add durable loading, success, empty, and error workflows around backend calls.
3. Testing: add end-to-end tests for the critical clinical workflows.
4. Compliance hardening: authentication, audit logs, data privacy controls, and clinical review flow.
5. Deployment readiness: Docker Compose verification, CI, environment configuration, and production build documentation.
6. AI/RAG enablement: install optional AI dependencies on a machine with Windows C++ Build Tools or use compatible prebuilt wheels.

## 8. Local Run Instructions

Frontend:

```bash
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Backend, once Python and dependencies are available:

```bash
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Expected API:

```text
http://127.0.0.1:8000
```

Tests:

```bash
npm test
npm run backend:test
```

Current test coverage focuses on the TDD-style business rules that should remain stable:

- packaged clinical dataset metrics
- quality defect detection
- cohort and protocol calculations
- treatment/report metrics
- CSV export formatting
- study report text generation
- shared desktop/mobile navigation configuration
- recent activity routing to related application sections
- reusable table filtering, sorting, pagination, and page clamping
- mocked FastAPI client contracts for upload/profile, paper analysis, cohort discovery, protocol checks, chat, and non-2xx errors
- mocked FastAPI client contract for report persistence
- backend FastAPI endpoint tests for every implemented route
- backend persistence assertions for dataset profiles, generated reports, cohorts, and analysis history
- backend quality-engine tests for profiling, cohort discovery, and protocol evaluation

Docker option:

```bash
docker compose up --build
```

## 9. Overall Project Status

Current status: functional local frontend with enabled interactive controls, typed FastAPI client integration, SQLAlchemy persistence wired for PostgreSQL through `DATABASE_URL`, mocked API contract tests, backend endpoint/persistence tests, and successful TypeScript/build verification.

Main remaining gap: hardening API schemas and error states, verifying Docker Compose/PostgreSQL on a machine with Docker installed, then adding end-to-end tests and clinical compliance controls.

## 10. AI Upgrade: Clinical Ingestion, RAG, Tool Calling, Streaming, Evals (2026-10-08)

This pass replaces the placeholder AI endpoints with working ones. It supersedes the earlier notes about optional OpenAI, LangChain and ChromaDB dependencies: the AI layer now uses the Anthropic SDK, local `fastembed` embeddings and `pgvector`, all of which install on Windows without build tools. `backend/requirements-ai.txt` is no longer used by any code.

### What was added

- `POST /ingest/fhir`: validates a FHIR R4 Bundle (Patient, Condition, Observation) with Pydantic models in `backend/app/schemas.py`, maps valid resources into a new `patients` table, and stores invalid records in `ingestion_rejects` with the reason (`backend/app/fhir.py`).
- `POST /ingest/cda`: parses a C-CDA XML document with lxml into the same patient model, with entity resolution and network access disabled in the parser (`backend/app/cda.py`).
- `backend/app/mapping.py`: shared SNOMED CT and ICD-10 code mapping, blood pressure selection and age calculation used by both ingestion paths.
- `POST /papers/analyze`: now real retrieval-augmented summarization. Papers are chunked, embedded and stored in `paper_chunks` (pgvector on PostgreSQL, JSON on SQLite); Claude summarizes only from the retrieved chunks and the response lists the source chunks (`backend/app/rag.py`).
- `POST /chat`: rebuilt around tool calling. Claude calls `discover_cohort`, `dataset_stats` and `search_papers`, and the response carries the sources and tool calls (`backend/app/agent.py`).
- `POST /chat/stream`: the same agent over server-sent events; the assistant panel renders the answer as it streams (`src/api.ts`, `src/App.tsx`).
- `backend/evals/golden.json` and `backend/evals/run_evals.py`: 20 questions about the sample dataset with known answers, and a runner that scores correctness and grounding and writes `backend/evals/results.json`.
- `sample_data/fhir_bundle_synthea_style.json` and `sample_data/ccda_synthea_style.xml`: synthetic, hand-written samples in the shape Synthea produces, including deliberately invalid records.

### Verification

- Backend: 126 unit and endpoint tests pass with the LLM and the embedding model mocked (`npm run backend:test`).
- Frontend: 33 tests pass, including the server-sent event parser and streaming client (`npm test`); `npm run build` succeeds.
- The 20 golden answers are checked two ways without the LLM: against the tools, and against an independent pandas calculation.
- The real embedding model was run locally end to end (download, index, search).
- Streaming was verified against a real uvicorn server and in the browser using a scripted stand-in for the model.

### Not yet verified

- No live Claude call has been made: no API key was available in the development environment. The eval score in `backend/evals/results.json` does not exist until `run_evals.py` is run with a key.
- The PostgreSQL and pgvector path has not been run, because Docker is not installed on this machine. The pgvector column type and the cosine-distance query are checked at the SQL level only.
- The sample FHIR and C-CDA files follow Synthea's structure but were not generated by Synthea.
