# ClinicalPilot AI - Project Report

Status date: July 16, 2026

## 1. Executive Summary

ClinicalPilot AI is a clinical research web application for dataset quality review, cohort discovery, clinical paper insight extraction, study report generation, and digital twin-style operational simulation.

The project currently contains a working React + TypeScript frontend, a FastAPI backend scaffold, sample cardiovascular clinical data, Docker configuration, and a production build pipeline. The frontend has been updated so the visible demo controls are interactive locally: upload controls open file selection, exports generate downloadable files, filters update cohort/data views, the assistant can answer local dataset/report questions, reports can be configured, and simulator sliders recalculate projected outcomes.

The application is running locally at:

```text
http://127.0.0.1:5173
```

## 2. Current Technology Stack

- Frontend: React 18, TypeScript, Vite, Material UI, Recharts, TanStack React Query
- Backend: FastAPI, Pandas, NumPy, Scikit-Learn, python-multipart
- AI/RAG dependencies declared: OpenAI, LangChain, ChromaDB
- Deployment assets: Dockerfile for frontend, backend Dockerfile, Docker Compose with PostgreSQL
- Dataset: `sample_data/cardiovascular_phase_ii.csv`

## 3. Repository Structure

- `src/App.tsx`: Main application UI and interactive workflows
- `src/clinicalData.ts`: Packaged clinical demo records and computed analytics
- `src/data.ts`: Navigation types, activity items, and paper insight demo content
- `src/theme.ts`: Material UI theme
- `src/styles.css`: Global styles
- `backend/app/main.py`: FastAPI app and API endpoints
- `backend/app/quality.py`: Dataset profiling, cohort discovery, and protocol evaluation logic
- `sample_data/cardiovascular_phase_ii.csv`: Demo cardiovascular clinical dataset
- `docker-compose.yml`: Frontend, API, and PostgreSQL service configuration
- `README.md`: Existing setup and feature overview

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
- Paper upload area now opens a file picker and updates the displayed paper name.
- Dataset table filter toggles between all rows and data-quality issue rows.
- Dataset preview exports to CSV.
- Cohort export generates a CSV.
- Study report export generates a text report.
- Header, sidebar, notification, AI assistant, and settings controls now show useful local feedback.
- Cohort filters are controlled and update the matching record count.
- Protocol analysis button gives eligibility feedback.
- Report title, report type, and AI insight toggle are editable.
- AI assistant accepts questions and returns local clinical-data answers.
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

Implemented backend data-quality logic:

- Missing-value counts
- Duplicate PatientID detection
- Invalid age detection
- Numeric outlier estimation with IsolationForest
- Quality score calculation
- Recommended cleaning actions
- Cohort filtering
- Protocol eligibility calculation

## 5. Current Verification

Completed checks:

```text
npm test
npm exec tsc -- --noEmit
npm run build
Invoke-WebRequest http://127.0.0.1:5173
```

Results:

- Node test suite passed with 16 tests.
- TypeScript check passed.
- Production Vite build passed.
- Local frontend server returned HTTP 200.
- Local frontend is running at `http://127.0.0.1:5173`.

Notes:

- Vite needed to run outside the Codex sandbox because the sandbox blocked Vite/esbuild from loading `vite.config.ts`.
- Python is not installed as a normal system command in this environment.
- The bundled Python runtime does not currently include FastAPI dependencies, so the backend was not started locally in this pass.
- A Playwright visual smoke test was attempted but blocked by a local permission error accessing the Codex app data directory.

## 6. What Is Yet To Be Done

### Production Frontend Integration

- Connect frontend upload, profiling, cohort, protocol, paper-analysis, and chat actions to the FastAPI backend.
- Replace local-only snackbar feedback with persisted workflow states.
- Add loading, success, empty, and error states for every API-backed operation.
- Add user-facing validation for unsupported upload formats and malformed files.
- Add pagination, sorting, and full search for patient/cohort tables.
- Add responsive mobile navigation because the current sidebar is hidden on small screens.

### Backend Completion

- Install and verify backend Python dependencies.
- Run the FastAPI API locally at `http://127.0.0.1:8000`.
- Add automated backend tests for profiling, cohort discovery, protocol checks, paper analysis, and chat.
- Add stronger validation with Pydantic request/response models.
- Add safer handling for missing columns and invalid uploaded files.
- Add persistent storage using the PostgreSQL service already declared in Docker Compose.
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

1. Backend setup and API verification: install dependencies, start FastAPI, confirm all endpoints.
2. Frontend/API integration: wire dataset profile, cohort discovery, protocol check, paper upload, and chat to backend endpoints.
3. Persistence: save uploaded datasets, generated reports, cohorts, and analysis history in PostgreSQL.
4. Testing: add automated tests for the critical clinical workflows.
5. Compliance hardening: authentication, audit logs, data privacy controls, and clinical review flow.
6. Deployment readiness: Docker Compose verification, CI, environment configuration, and production build documentation.

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
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Expected API:

```text
http://127.0.0.1:8000
```

Tests:

```bash
npm test
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

Docker option:

```bash
docker compose up --build
```

## 9. Overall Project Status

Current status: functional local frontend demo with enabled interactive controls, successful TypeScript/build verification, and a backend scaffold ready for dependency setup and integration.

Main remaining gap: converting the locally interactive demo into a fully API-connected, persisted, tested, and compliant clinical research platform.
