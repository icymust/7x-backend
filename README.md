# Predicto

AI-powered workforce & courier capacity planning platform. It turns a raw
demand/roster Excel upload into a day-by-day staffing plan — forecasting
demand, calculating courier shortages and surpluses, and recommending
concrete actions (transfer couriers between stores, outsource temporarily,
or hire permanently), each with an AI-generated, human-readable explanation.

## Key features

- **Excel-to-plan pipeline** — upload a workforce/demand Excel file and get
  a full capacity plan: demand forecasting (CatBoost, with a seasonal
  baseline fallback), required-vs-available courier calculation, and a
  rule-based Decision Engine that proposes emergency outsourcing, planned
  outsourcing, permanent hiring, or cross-store transfers.
- **Interactive network map** — MapLibre-based map of all stores with a
  demand heatmap/points toggle, live driver-status markers (surplus /
  balanced / shortage / critical), and a date filter.
- **Per-store AI Suggestions** — each recommended action gets a natural-
  language explanation generated on demand by a local Ollama LLM (structured
  JSON: recommendation, timing, reasons), with a deterministic fallback when
  Ollama is disabled or unavailable so the feature never breaks.
- **Demand calendar** — a real, backend-driven monthly calendar per store
  with daily severity coloring and rollup stats (coverage %, critical days,
  shortage, predicted orders).
- **Manage actions** — request forms for transferring, outsourcing, or
  hiring couriers, pre-filled with the numbers the AI suggestion itself
  calculated.
- **Operational dashboard** — network-wide KPIs, workforce/driver-status
  breakdown, and a live notifications feed (urgent shortages, upcoming
  shortages, hiring deadlines, surplus).
- **Dark/light theme**, fully responsive sidebar navigation.

## Tech stack

| Layer    | Stack |
|----------|-------|
| Backend  | FastAPI, SQLAlchemy, Alembic, PostgreSQL, CatBoost, pandas, httpx (optional Ollama client) |
| Frontend | Vue 3 + TypeScript, Vite, PrimeVue, MapLibre GL, Chart.js |

## Running it

### Option A — Docker Compose (recommended)

From the repository root:

```bash
docker compose up --build -d
```

This builds and starts PostgreSQL, the FastAPI backend (runs Alembic
migrations automatically, then Uvicorn), an Nginx-served Vite build of the
frontend, and an Nginx reverse proxy that fronts both of them on a single
port.

| Service               | URL                                 |
|------------------------|--------------------------------------|
| App (via proxy)        | http://127.0.0.1:8080               |
| Swagger UI (via proxy) | http://127.0.0.1:8080/docs          |
| Frontend (direct)      | http://127.0.0.1:3000               |
| Backend API (direct)   | http://127.0.0.1:8000               |
| Swagger UI (direct)    | http://127.0.0.1:8000/docs          |
| OpenAPI JSON (direct)  | http://127.0.0.1:8000/openapi.json  |
| PostgreSQL              | localhost:5433                     |

For port forwarding or demoing the app (e.g. over SSH tunnel or ngrok), use
the proxy port (`8080` by default, `PROXY_PORT` in `.env`) — it's the only
port that needs to be forwarded, since it serves the frontend and routes
`/api`, `/health`, and `/docs` to the backend on the same origin.

Check everything is healthy:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
```

Stop the stack (keeps the database volume and any saved Planning Runs):

```bash
docker compose stop
```

### Option B — Local development

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres        # or point DATABASE_URL at your own Postgres
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

The frontend calls the backend at `VITE_API_BASE_URL` (defaults to
`http://localhost:8000` — see `frontend/.env.example`).

### Configuration

Copy `.env.example` to `.env` at the repo root to override defaults (ports,
Postgres credentials, CORS origins, Ollama settings). Docker Compose works
out of the box without a `.env` file.

Ollama is optional and external to Compose. If it's disabled
(`OLLAMA_ENABLED=false`, the default) or unreachable, AI Suggestions fall
back to a structured, non-LLM explanation instead of failing.

### Tests

```bash
cd backend
pytest
```

## Project structure

```text
.
├── backend/     FastAPI app, Alembic migrations, tests
├── frontend/    Vue 3 + Vite single-page app
├── docs/        API contract and architecture notes
└── compose.yaml Docker Compose for the full stack
```

See [`docs/ENDPOINTS.md`](docs/ENDPOINTS.md) for the full API reference.
