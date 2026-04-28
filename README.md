# Support Intelligence Platform

An end-to-end support copilot: upload your knowledge base, chat with an LLM that searches it and cites chunks, turn a conversation into a tracked case, and review every turn in a QA console backed by traces and evaluation metrics.

## What's inside

| Area | Summary |
|------|---------|
| **Foundations** | Repo scaffolding, pgvector-enabled local Postgres via Docker, Supabase-compatible migrations, typed FastAPI service, and Supabase JWT auth (HS256 legacy secret **or** ES256 / RS256 via JWKS auto-resolved from the token `iss`). |
| **Product shell** | Next.js App Router with Supabase Auth (email/password + `/auth/callback`), protected app routes, `/api/v1/health` probes, and typed endpoints behind a versioned router. |
| **Knowledge ingestion & retrieval** | Text + PDF extraction → chunking → OpenAI embeddings → pgvector storage with HNSW index → `POST /retrieve` for vector search, plus per-document tags and `source_type` metadata. |
| **Copilot** | OpenAI **Responses API** with function tools (`search_documents`, `get_case_summary`, `extract_action_items`, `draft_support_reply`), structured outputs, and a LangGraph workflow `prepare_context → tool_agent → retrieval → synthesize → quality_signals`. Streams over SSE with token, tool-call, and source events; persists transcript + tool trace to `chat_messages.metadata`. |
| **Voice & session insights** | Whisper transcription for short voice clips, and a one-click endpoint that generates + persists a session summary, action items, and case tags onto `chat_sessions.metadata`. |
| **Cases workflow** | Promote a copilot session into a case (one-to-one via `created_from_session_id`), track `summary` / `priority` / `category` / `status`, manage `case_action_items`, link cited documents via `case_documents`, and feed a compact case brief back into the copilot. |
| **Observability & QA console** | LangSmith tracing of retrieval, tool dispatch, and synthesis; per-turn metrics (`retrieval_ms`, `tools_dispatch_ms`, `tool_calls`) attached to every assistant message; a `/qa` console for browsing sessions, transcripts, sources, tool calls, and raw observability metadata. |
| **Evaluation harness** | Dataset-driven eval CLI with pluggable metrics — `GroundednessOverlap`, `CitationPresence`, `RequiredStructuredFields`, `StructuredFormat`, `EscalationMatch` — that scores copilot structured outputs against grounding corpora. |

## Prerequisites

- [Node.js](https://nodejs.org/) 20+
- [Python](https://www.python.org/) 3.11+ (3.12 recommended)
- A [Supabase](https://supabase.com/) project (Auth + Postgres with `pgvector`), **or** Docker for a local pgvector-enabled Postgres
- [Docker](https://docs.docker.com/get-docker/) (optional: local DB)
- An [OpenAI](https://platform.openai.com/) API key — embeddings, copilot, Whisper
- Optional: a [LangSmith](https://smith.langchain.com/) account for tracing

## Repository layout

```
.
├── backend/
│   └── app/
│       ├── api/v1/             # documents, retrieve, copilot, cases, sessions, qa, health
│       ├── api/deps.py         # Supabase JWT (HS256 + JWKS) + DB session deps
│       ├── core/config.py      # Settings (Pydantic) — loaded from backend/.env
│       ├── services/
│       │   ├── ingestion.py, chunking.py, embeddings.py, text_extract.py, retrieval.py
│       │   ├── copilot/        # Responses API client, prompts, orchestrator, streaming
│       │   │   ├── workflow/   # LangGraph nodes + graph (prepare/agent/retrieval/synth/quality)
│       │   │   ├── tools/      # Function tool definitions, executor, schemas
│       │   │   ├── bootstrap_retrieval.py, session_insights.py, voice_transcription.py
│       │   ├── cases/          # create_from_session, detail, access, context_block, document_refs
│       │   └── observability/  # LangSmith setup, turn metrics, turn observability metadata
│       ├── models/             # SQLAlchemy (users, documents, chat, case)
│       ├── schemas/            # Pydantic request/response models
│       └── eval/               # dataset_schema, runner, metrics, CLI
├── database/migrations/        # 001 schema, 002 pgvector, 003 local-no-auth, 004 cases
├── docker-compose.yml          # pgvector/pgvector:pg16 (host :5433 → container :5432)
├── frontend/                   # Next.js App Router UI (Supabase Auth)
└── README.md
```

## 1. Supabase project (recommended)

1. Create a project and note the **Project URL** and **anon / publishable key** (Settings → API).
2. Authentication → enable **Email** (password) for development.
3. Add redirect URL: `http://localhost:3000/auth/callback` (add your production URL later).
4. Enable the `vector` extension when prompted by migration `002`.

> Local-only alternative: skip Supabase, run `docker compose up -d`, and apply `003_local_docker_no_auth.sql` (see below). Authenticated routes still require a Supabase-signed JWT either way.

## 2. Database migrations

Run against **Supabase** (SQL Editor or CLI) or any Postgres whose connection string matches `DATABASE_URL`.

| # | File | When to run |
|---|------|-------------|
| 001 | `database/migrations/001_initial_schema.sql` | Supabase — depends on `auth.users`. |
| 002 | `database/migrations/002_pgvector_rag.sql` | Enables `vector`, adds embeddings + HNSW index. |
| 003 | `database/migrations/003_local_docker_no_auth.sql` | **Local Docker only.** Supabase-free schema (replaces 001/002). |
| 004 | `database/migrations/004_cases_workflow.sql` | Adds `summary` / `priority` / `category` / `created_from_session_id` on `cases`, plus `case_action_items` and `case_documents`. Stubs `auth.uid()` on plain Postgres so RLS policies still apply. |
| 005 | `database/migrations/005_messages_session_position_unique.sql` | Enforces unique `(session_id, position)` ordering for transcript messages and stops if duplicates already exist. |

**Local Docker (pgvector):** the compose file uses `pgvector/pgvector:pg16`. If you previously ran plain `postgres:16`, run `docker compose down -v` once (this wipes local DB data) and then `docker compose up -d`.

**Supabase:** migrations use `vector(1536)` to match OpenAI `text-embedding-3-small` defaults. Change `EMBEDDING_DIMENSIONS` consistently if you pick a different model.

Schema highlights:

- `public.users` — profile row per auth user (synced via trigger on sign-up).
- `documents`, `document_versions`, `document_chunks` — knowledge lifecycle; `document_chunks.embedding` is `vector(1536)` with an HNSW index and tag / source_type metadata.
- `cases`, `case_action_items`, `case_documents` — support workflow with summary / priority / category and a link back to the originating copilot session.
- `chat_sessions` / `chat_messages` — copilot transcript. `chat_messages.metadata` carries the tool trace, retrieval sources, timing, and LangSmith run IDs; `chat_sessions.metadata` carries generated insights (summary, action items, tags).

Row Level Security (RLS) policies are included. The FastAPI service role (when wired with a Supabase service key) bypasses RLS for batch work.

## 3. Frontend (Next.js)

```bash
cd frontend
npm install
copy env.example .env.local   # Windows; Unix: cp env.example .env.local
```

Fill in `frontend/.env.local`:

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | **Integrations → Data API → API URL** (`https://….supabase.co`) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **Settings → API Keys → Publishable key** (`sb_publishable_…`) or Legacy **anon** JWT. Never use a secret / service_role key in the browser. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Optional alias for the same publishable/anon value. |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL (default `http://localhost:8000`). |

```bash
npm run dev
```

Routes:

| Path | Purpose |
|------|---------|
| `/login` | Email + password (Supabase Auth). |
| `/auth/callback` | Supabase OAuth/magic-link callback. |
| `/dashboard` | Overview + API health check. |
| `/documents` | Upload / list documents for RAG. |
| `/copilot` | Chat with the copilot — SSE streaming, tool traces, voice input, session history. |
| `/cases` | Case list. |
| `/cases/[id]` | Case detail — summary, priority, action items, cited documents. |
| `/qa` | QA console — browse copilot sessions, transcripts, sources, tool calls, and observability metadata. |

## 4. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows (Unix: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # Windows; Unix: cp .env.example .env
```

Fill in `backend/.env`. Minimum for a working copilot:

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | ✅ | Async URL, e.g. `postgresql+asyncpg://…`. Strip `+asyncpg` only when running migrations via plain `psql`. |
| `SUPABASE_JWT_SECRET` | ⚠️ | Legacy HS256 secret. Leave empty on new Supabase signing keys (API verifies via JWKS from the token `iss`). |
| `OPENAI_API_KEY` | ✅ | Embeddings + copilot + Whisper. |
| `CORS_ORIGINS` | ✅ | Include your Next.js origin (default `http://localhost:3000,http://127.0.0.1:3000`). |
| `COPILOT_MODEL` | — | Default `gpt-4o-mini`. |
| `COPILOT_RETRIEVAL_TOP_K` | — | Default `8` (1 – 32). |
| `COPILOT_MIN_EVIDENCE_SCORE` | — | Below this max retrieval score the answer is flagged `weak_evidence`. |
| `COPILOT_MAX_HISTORY_MESSAGES` | — | Transcript window sent to the model (default `12`). |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | — | Must match the DB `vector(N)` column. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | — | Ingestion chunking (defaults `1200` / `200`). |
| `ASYNCPG_STATEMENT_CACHE_SIZE` | — | Set to `0` with Supabase pooler / PgBouncer transaction mode (auto-detected for common Supabase pooler URLs). |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | — | Optional tracing of retrieval, tool calls, and synthesis (project defaults to `signal-desk`). |

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs).

### API surface

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health`, `/api/v1/health` | Liveness. |
| `GET` | `/api/v1/documents` | List documents for the authenticated user. |
| `POST` | `/api/v1/documents/ingest` | Multipart upload → extract → chunk → embed → store. |
| `POST` | `/api/v1/retrieve` | Vector search (query + optional filters). |
| `POST` | `/api/v1/copilot/chat` | Run one copilot turn (tool calls + structured output). |
| `POST` | `/api/v1/copilot/chat/stream` | Same turn over SSE — streams tokens, tool calls, sources, and a final `done` event. |
| `POST` | `/api/v1/copilot/voice/transcribe` | Whisper transcription (multipart audio, ≤ 15 MB). |
| `POST` | `/api/v1/copilot/sessions/{id}/insights` | Generate + persist session summary, action items, and case tags. |
| `GET`  | `/api/v1/copilot/sessions` | List copilot sessions for the user. |
| `GET`  | `/api/v1/copilot/sessions/{id}` | Session metadata incl. persisted insights. |
| `GET`  | `/api/v1/copilot/sessions/{id}/messages` | Ordered transcript with tool-trace metadata. |
| `GET`  | `/api/v1/cases` | Paginated case list. |
| `POST` | `/api/v1/cases/from-session` | Promote a copilot session into a new case. |
| `GET`  | `/api/v1/cases/{id}` | Case detail (action items, cited documents). |
| `GET`  | `/api/v1/cases/{id}/copilot-context` | Compact case brief for feeding back into the copilot. |
| `GET`  | `/api/v1/qa/copilot-sessions` | QA console session index. |
| `GET`  | `/api/v1/qa/copilot-sessions/{id}` | Full transcript with raw tool / observability metadata. |

### Copilot workflow

One turn runs a small linear LangGraph:

```
prepare_context → tool_agent (Responses API) → retrieval → synthesize → quality_signals
```

- **prepare_context** trims history, fans case context into a system block, and builds a `ToolContext`.
- **tool_agent** calls OpenAI Responses with `search_documents`, `get_case_summary`, `extract_action_items`, and `draft_support_reply` available as function tools.
- **retrieval** aggregates cited chunks, scores them, and sets `weak_evidence` when the max score falls below `COPILOT_MIN_EVIDENCE_SCORE`.
- **synthesize** produces the final markdown answer + structured payload.
- **quality_signals** emits timing + a confidence hint.

Every turn persists the full tool trace, retrieval sources, LangSmith run IDs, and stage timings onto `chat_messages.metadata`, so the QA console and eval harness can replay and score the turn deterministically.

## 5. Optional: Docker Postgres

```bash
docker compose up -d
```

Starts a pgvector-enabled Postgres (host port **5433** → container **5432**, so it does not clash with a local PostgreSQL on 5432). Point `backend/.env` `DATABASE_URL` at that port and apply `003_local_docker_no_auth.sql` followed by `004_cases_workflow.sql`. The `auth.uid()` stub in 004 keeps RLS policies valid without a Supabase `auth` schema.

## 6. Evaluation harness

Run the built-in copilot eval dataset and print per-case + aggregate metrics JSON:

```bash
cd backend
python -m app.eval.cli --dataset app/eval/datasets/example.json
```

Exit code is non-zero if any case fails its expectations (groundedness floor, required structured fields, citation mentions, escalation match, …). Add new metrics by implementing the `EvalMetric` protocol in `app/eval/metrics.py` and wiring it into `runner.py`.

## Scripts

| Location | Command | Description |
|----------|---------|-------------|
| `frontend` | `npm run dev` | Next.js dev server. |
| `frontend` | `npm run build` | Production build. |
| `backend`  | `uvicorn app.main:app --reload` | API server. |
| `backend`  | `python -m app.eval.cli --dataset …` | Copilot eval harness. |

| `backend`  | `python -m unittest discover -s tests -v` | Backend unit tests. |

## Environment summary

| App | File | Notes |
|-----|------|--------|
| Frontend | `frontend/.env.local` | Supabase URL + publishable / anon key + `NEXT_PUBLIC_API_URL`. |
| Backend  | `backend/.env` | `DATABASE_URL`, `SUPABASE_JWT_SECRET` (or JWKS via token `iss`), `OPENAI_API_KEY`, `CORS_ORIGINS`, copilot / embedding overrides, optional LangSmith tracing. |
