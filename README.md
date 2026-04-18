# Support Intelligence Platform

Phase 1 delivers the **product shell** (Next.js + Supabase Auth), an initial **Postgres schema** (Supabase-compatible migration SQL), and **FastAPI** list endpoints with typed response models.

**Phase 2** adds **document ingestion** (plain text + PDF), **chunking**, **OpenAI embeddings**, **pgvector** storage, and a **retrieval** API. The ingestion pipeline is structured so the same functions can run in a background worker later.

## Prerequisites

- [Node.js](https://nodejs.org/) 20+
- [Python](https://www.python.org/) 3.11+
- A [Supabase](https://supabase.com/) project (Auth + Postgres), or local tooling that provides `auth.users`
- [Docker](https://docs.docker.com/get-docker/) (optional: local Postgres for non-Supabase experiments)

## Repository layout

```
.
├── backend/                 # FastAPI API
├── database/migrations/     # SQL migrations (001 schema, 002 pgvector RAG)
├── docker-compose.yml       # Optional local Postgres
├── frontend/                # Next.js App Router UI
└── README.md
```

## 1. Supabase project

1. Create a project and note **Project URL** and **anon key** (Settings → API).
2. Authentication → enable **Email** (password) for development.
3. Add redirect URL: `http://localhost:3000/auth/callback` (and your production URL later).

## 2. Database migrations (Supabase SQL Editor or CLI)

1. Run `database/migrations/001_initial_schema.sql` (expects `auth.users`).
2. Run `database/migrations/002_pgvector_rag.sql` (enables `vector`, adds `tags`, `source_type`, `embedding`, HNSW index).

**Local Docker:** the compose file uses `pgvector/pgvector:pg16`. If you previously used plain `postgres:16`, run `docker compose down -v` once to recreate the volume (this wipes local DB data), then `docker compose up -d`.

**Supabase:** enable the `vector` extension if prompted; the migration uses `vector(1536)` to match OpenAI `text-embedding-3-small` defaults.

This creates:

- `public.users` — profile row per auth user (synced via trigger on sign-up)
- `documents`, `document_versions`, `document_chunks` — knowledge lifecycle (chunks ready for a later pgvector column)
- `cases`, `sessions`, `messages` — support workflow + transcript (`messages.metadata` reserved for traces / tools)

Row Level Security (RLS) policies are included as a baseline. The FastAPI service role (when you wire the backend to Supabase with the service key) bypasses RLS for batch jobs.

## 3. Frontend (Next.js)

```bash
cd frontend
npm install
copy env.example .env.local   # Windows; Unix: cp env.example .env.local
```

Copy `frontend/env.example` to `.env.local` and set:

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | **Integrations → Data API → API URL** (`https://….supabase.co`) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **Settings → API Keys → Publishable key** (`sb_publishable_…`) or Legacy **anon** JWT; not the **secret** key |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Optional alias for the same publishable/anon value if you prefer the name |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL (default `http://localhost:8000`) |

```bash
npm run dev
```

Routes:

| Path | Purpose |
|------|---------|
| `/login` | Email + password (Supabase Auth) |
| `/dashboard` | Overview + API health check |
| `/documents` | Documents shell |
| `/cases` | Cases & sessions shell |
| `/copilot` | Placeholder for assisted UI |

## 4. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows
pip install -r requirements.txt
copy .env.example .env
```

Set in `backend/.env` at minimum:

- `DATABASE_URL` — async URL, e.g. `postgresql+asyncpg://…`
- `SUPABASE_JWT_SECRET` — same secret the frontend tokens are signed with
- `OPENAI_API_KEY` — for embeddings

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ensure `CORS_ORIGINS` includes your Next.js origin (e.g. `http://localhost:3000`).

### API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health`, `/api/v1/health` | Liveness |
| `GET` | `/api/v1/documents` | List documents for authenticated user |
| `POST` | `/api/v1/documents/ingest` | Multipart upload → extract → chunk → embed → store |
| `POST` | `/api/v1/retrieve` | Vector search (query + optional filters) |
| `GET` | `/api/v1/sessions` | Sessions list (placeholder) |
| `GET` | `/api/v1/cases` | Cases list (placeholder) |

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## 5. Optional: Docker Postgres

`docker compose up -d` starts a local Postgres for experiments. The migration file targets **Supabase** (`auth.users`); it is not intended for the plain Docker database unless you add a compatible auth schema.

## Scripts

| Location | Command | Description |
|----------|---------|-------------|
| `frontend` | `npm run dev` | Next.js dev server |
| `frontend` | `npm run build` | Production build |
| `backend` | `uvicorn app.main:app --reload` | API server |

## Environment summary

| App | File | Notes |
|-----|------|--------|
| Frontend | `frontend/.env.local` | Supabase URL + publishable/anon key + `NEXT_PUBLIC_API_URL` |
| Backend | `backend/.env` | `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`, `CORS_ORIGINS`, chunk/embedding overrides |
