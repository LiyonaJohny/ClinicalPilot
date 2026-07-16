# ClinicalPilot AI

ClinicalPilot AI is a web-based clinical research suite for uploading datasets, identifying data-quality issues, analyzing cohorts, extracting study-paper insights, generating study reports, and chatting with research data.

## Architecture

React + TypeScript frontend, FastAPI backend, Pandas/NumPy/Scikit-Learn data processing, optional OpenAI/LangChain RAG services, and PostgreSQL for persistence.

## Local Development

```bash
npm install
npm run dev
```

The frontend runs at `http://127.0.0.1:5173`.

The API can run with:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Implemented Demo Modules

- Research dashboard with enrollment, disease distribution, missing-data, and activity views
- Dataset quality engine UI for missing values, duplicates, invalid entries, and health mapping
- AI data cleaning assistant panel
- Research paper analyzer with AI insight extraction cards
- Cohort discovery and protocol eligibility checker
- Study report generator with AI-generated draft preview
- Digital twin research simulator for recruitment and staffing scenarios
- FastAPI endpoints for dataset profiling, cohort discovery, protocol checks, paper analysis, and dataset chat
