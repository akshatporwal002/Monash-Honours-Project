# QuantumLearn

QuantumLearn is a web-based learning management system for introductory quantum computing. This repository currently contains only the base application skeleton.

## Project structure

```text
backend/     FastAPI API, application services and tests
frontend/    React and TypeScript web application
docs/        Project and architecture notes
```

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- npm 10 or newer

## Run the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

## Run the frontend

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The web application will be available at `http://localhost:5173`.

## Checks

```powershell
cd backend
pytest
ruff check .

cd ..\frontend
npm run lint
npm run build
```

## Current scope

The application provides a React scaffold, a FastAPI health endpoint, the initial persistence
foundation, and a provider-independent feedback pipeline. The pipeline can collect context, build
a privacy-conscious structured feedback prompt, validate model output through a replaceable LLM
client, judge it through the existing test boundary, store the final aggregate atomically, and
replay stored results idempotently. It is currently a backend service only and is not exposed
through an API. No production LLM adapter is configured yet.

Database schema changes are managed through Alembic. Shared course, task, submission and user
entities remain owned by their respective feature teams and are represented by external references
in the Person 4 tables until their canonical models are available.
