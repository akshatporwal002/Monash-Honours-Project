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
# Replace SESSION_SECRET_KEY in .env before starting the API
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

cd ..\frontend
npm run lint
npm run build
```

## Current scope

This scaffold provides a blank React page, a FastAPI health endpoint and basic configuration. Feature folders will be added when development begins on each feature.
