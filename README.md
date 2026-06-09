# partifi-nextgen

Greenfield rewrite of [Partifi](https://github.com/5harad/partifi) — automated score-to-parts workflow with modern infrastructure and UI parity.

Legacy reference: `../partifi` (PHP + jQuery + Python 2).

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React, TypeScript, Vite |
| API | FastAPI (Python 3.12) |
| Workers | Python 3.12 + Redis queue |
| Pipeline | Shared cut/paste Python package |
| Database | MySQL 8 |
| Files | S3 (`cdn.partifi.org`; MinIO locally) |
| Deploy | Docker Compose on EC2 |

## Project layout

```
partifi-nextgen/
├── frontend/          # React app (ported partifi.css + images)
├── api/               # FastAPI
├── workers/           # Background job workers
├── pipeline/          # Shared cut/paste logic (api + workers)
├── docker/            # MySQL init SQL
└── docker-compose.yml
```

## Local development

### Prerequisites

- Docker Desktop
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (optional, for running Python services outside Docker)

### 1. Start backend services

```bash
cp .env.example .env   # if .env doesn't exist
docker compose up -d --build
```

Services:

| Service | URL |
|---------|-----|
| API | http://localhost:8001 |
| API health | http://localhost:8001/health/ready |
| MinIO console | http://localhost:9001 |
| MySQL | localhost:3306 |

### 2. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — upload a PDF to run the full workflow (import → segment → preview → generate → download).

### 3. Scale workers (optional)

```bash
docker compose up -d --scale worker=3
```

### Python services (uv, outside Docker)

Each Python service has its own `pyproject.toml` and `uv.lock`:

```bash
# API
cd api && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Worker
cd workers && uv sync && uv run python worker.py
```

To add a dependency: `uv add <package>` in `api/` or `workers/`, then commit the updated `pyproject.toml` and `uv.lock`.

### Tests

```bash
cd api && uv sync --group dev && uv run pytest
```

## API (v1)

Health:

- `GET /health` — liveness
- `GET /health/ready` — MySQL, Redis, S3 checks

Partsets (CSRF required on mutations):

- `GET /api/v1/csrf-token`
- `POST /api/v1/partsets` — upload PDF, create partset
- `GET /api/v1/partsets/{private_id}/import-status`
- `GET /api/v1/partsets/{private_id}/segment-data`
- `PUT /api/v1/partsets/{private_id}/pages/{page}/segments`
- `GET /api/v1/partsets/{private_id}/preview-data`
- `PUT /api/v1/partsets/{private_id}/layout`
- `POST /api/v1/partsets/{private_id}/parts/combine`
- `POST /api/v1/partsets/{private_id}/generate`
- `GET /api/v1/partsets/{private_id}/partgen-status`
- `GET /api/v1/partsets/{private_id}/parts`

## Phase roadmap

1. **Foundation** — done (monorepo, CSS parity, Docker, uv)
2. **Import + pipeline** — PDF upload + workers done; IMSLP import pending
3. **Segment editor** — done
4. **Preview + generation** — done
5. **Supporting pages** — search, library, public download URLs (next)
6. **Migration + cutover** — DB import, DNS, decommission Linode

## Production infra

One EC2 instance (Docker Compose) + existing S3 bucket (~1.38 TB). See the project plan for details.
