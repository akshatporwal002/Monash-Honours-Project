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

The application now includes a responsive student learning experience connected to the FastAPI
backend. The demo student can open quiz, code, and circuit activities; save or submit work; run
quantum-circuit simulations; review feedback and progress; follow personalised recommendations;
and earn points and achievements. Notifications and an educator progress summary are also exposed
through the API.

Open `GET /api/v1/students/demo` in the API documentation to seed and inspect the demo experience.
The React client uses `http://localhost:8000/api/v1` by default; set `VITE_API_URL` to override it.

The provider-independent mocked feedback pipeline can collect context, generate deterministic
feedback, judge it, store the final aggregate atomically, and replay stored results idempotently.
It remains a backend service and is not yet exposed through an API.

Database schema changes are managed through Alembic. Shared course, task, submission and user
entities remain owned by their respective feature teams and are represented by external references
in the Person 4 tables until their canonical models are available.
