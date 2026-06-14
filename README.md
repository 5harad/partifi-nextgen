# partifi-nextgen

Greenfield rewrite of [Partifi](https://github.com/5harad/partifi) — automated score-to-parts workflow with modern infrastructure and UI parity.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React, TypeScript, Vite |
| API | FastAPI (Python 3.12) |
| Workers | Python 3.12 + Redis queue |
| Pipeline | Shared cut/paste Python package |
| Database | MySQL 8 |
| Files | S3 score PDFs (`cdn.partifi.org`; MinIO locally); EC2 cache for PNGs/parts |
| Deploy | Docker Compose on EC2 |

## File storage

**S3** (`cdn.partifi.org` in production; MinIO locally) stores **score PDFs only**:

```text
scores/{score_id}_score.pdf
```

**Local cache** (`PARTIFI_CACHE_ROOT`, default `/data/partifi`) holds page PNGs, preview segment cuts, and generated part PDFs. Import and partgen write here only — not to S3.

```text
/data/partifi/
  scores/{score_id}/lowres|highres|thumbs/
  preview/{partset_id}/s0.png …
  parts/{partset_id}/*.pdf
```

Legacy scores that have a PDF on S3 but no cached PNGs are warmed on first segment/preview visit (`warm_score_pages`: PDF → local PNGs). The API serves cache hits via `/page-image/`, `/preview-segment/`, and `/part-file/` routes. Cold entries are evicted by `jobs.clean_cache` (TTL + size cap); evicting parts sets `parts_ready = 0` so downloads regenerate from layout.

See **[docs/DEPLOY.md](docs/DEPLOY.md)** for cache sizing, cron, and optional S3 cleanup of test PNGs/parts.

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

**Sign in / library:** Set `GOOGLE_CLIENT_ID` in `.env` and `VITE_GOOGLE_CLIENT_ID` in `frontend/.env`, then use **Sign In** in the header. Creating a partset while signed in saves it to your library. For local testing without Google OAuth, `POST /api/v1/auth/dev-login` is available when `APP_ENV=development`.

### 3. Workers

Compose starts **three worker containers** (`worker-1`, `worker-2`, `worker-3`) that share the Redis queue. Each job runs in an isolated subprocess with a wall-clock timeout (`JOB_TIMEOUT_SECONDS`, default 45 minutes). On failure or timeout the partset is marked with an `error` stage so progress pages stop spinning.

```bash
docker compose up -d worker-1 worker-2 worker-3
# or recreate all services:
docker compose up -d
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

If you use Docker with the persisted `api_venv` / `worker_venv` volumes, refresh installed packages after pulling dependency changes:

```bash
docker compose exec api uv sync --frozen --no-dev
docker compose exec worker-1 uv sync --frozen --no-dev
docker compose restart api worker-1 worker-2 worker-3
```

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
- `GET /api/v1/auth/me` — current user (session cookie)
- `POST /api/v1/auth/google` — exchange Google auth code (or legacy id_token) for session
- `POST /api/v1/auth/dev-login` — development-only mock login
- `POST /api/v1/auth/logout`
- `GET /api/v1/library` — signed-in user's saved partsets
- `GET /api/v1/library/favorites/{access_id}` — favorite status
- `POST /api/v1/library/favorites/{access_id}` — add/remove favorite
- `POST /api/v1/partsets` — upload PDF, create partset
- `GET /api/v1/imslp/{imslp_id}/info` — IMSLP metadata lookup
- `POST /api/v1/partsets/imslp` — import score from IMSLP
- `GET /api/v1/search` — search public library
- `POST /api/v1/partsets/from-score` — partify from existing library score
- `GET /api/v1/partsets/{private_id}/import-status`
- `GET /api/v1/partsets/{private_id}/segment-data`
- `PUT /api/v1/partsets/{private_id}/pages/{page}/segments` — save one page while editing
- `PUT /api/v1/partsets/{private_id}/segments` — save all pages (with propagated tags) on continue to preview
- `GET /api/v1/partsets/{private_id}/preview-data`
- `PUT /api/v1/partsets/{private_id}/layout`
- `POST /api/v1/partsets/{private_id}/parts/combine`
- `POST /api/v1/partsets/{private_id}/generate`
- `GET /api/v1/partsets/{private_id}/partgen-status`
- `POST /api/v1/partsets/{private_id}/retry-pipeline` — re-enqueue failed import or partgen
- `GET /api/v1/partsets/{private_id}/parts`
- `GET /api/v1/access/{access_id}/parts`

Score PDF downloads (proxied from S3; no CSRF):

- `GET /api/v1/scores/{score_id}/score.pdf`
- `GET /api/v1/partsets/{private_id}/score.pdf`
- `GET /api/v1/access/{access_id}/score.pdf`

Cached assets (local cache; S3 read fallback only if legacy objects exist; no CSRF):

- `GET /api/v1/partsets/{private_id}/page-image/{page}.png?res=lowres|highres|thumbs`
- `GET /api/v1/partsets/{private_id}/preview-segment/{ndx}.png`
- `GET /api/v1/partsets/{private_id}/part-file/{filename}`
- `GET /api/v1/access/{access_id}/part-file/{filename}`

Segment or layout saves invalidate preview and part PDF cache entries for that partset.

## Production deploy

Full runbook: **[docs/DEPLOY.md](docs/DEPLOY.md)** (EC2, Docker Compose, legacy data import, DNS).

```bash
cp .env.production.example .env   # fill in secrets
docker compose -f docker-compose.prod.yml up -d --build
```
