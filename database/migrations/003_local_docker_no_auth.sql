-- Local Docker Postgres (pgvector compose) — schema without Supabase auth.users / RLS.
-- Apply after `docker compose up -d` when DATABASE_URL points at this instance.
-- Run: psql "postgresql://USER:PASS@HOST:PORT/DB" -f database/migrations/003_local_docker_no_auth.sql
-- (Strip +asyncpg from SQLAlchemy URLs.)

begin;

create extension if not exists pgcrypto;
create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type public.case_status as enum ('open', 'pending', 'resolved', 'closed');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.document_status as enum ('draft', 'published', 'archived');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.session_status as enum ('active', 'closed');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.message_role as enum ('user', 'assistant', 'system', 'tool');
exception when duplicate_object then null;
end $$;

-- ---------------------------------------------------------------------------
-- Users (standalone UUID — no auth.users FK; sync sign-ups manually or via app)
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id uuid primary key,
  email text,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists users_email_idx on public.users (lower(email));

-- ---------------------------------------------------------------------------
-- Documents & versioning
-- ---------------------------------------------------------------------------
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.users (id) on delete cascade,
  title text not null,
  status public.document_status not null default 'draft',
  current_version_id uuid,
  tags text[] not null default '{}'::text[],
  source_type text not null default 'upload',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists documents_owner_idx on public.documents (owner_id);
create index if not exists documents_status_idx on public.documents (status);
create index if not exists documents_tags_gin on public.documents using gin (tags);
create index if not exists documents_owner_source_idx on public.documents (owner_id, source_type);

create table if not exists public.document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents (id) on delete cascade,
  version int not null,
  source_uri text,
  content_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid references public.users (id),
  created_at timestamptz not null default now(),
  unique (document_id, version)
);

create index if not exists document_versions_document_idx on public.document_versions (document_id);

alter table public.documents
  drop constraint if exists documents_current_version_fk;
alter table public.documents
  add constraint documents_current_version_fk
  foreign key (current_version_id)
  references public.document_versions (id)
  on delete set null;

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions (id) on delete cascade,
  chunk_index int not null,
  content text not null,
  token_count int,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  unique (document_version_id, chunk_index)
);

create index if not exists document_chunks_version_idx on public.document_chunks (document_version_id);

create index if not exists document_chunks_embedding_hnsw
  on public.document_chunks
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create index if not exists document_chunks_version_embedding_idx
  on public.document_chunks (document_version_id)
  where embedding is not null;

-- ---------------------------------------------------------------------------
-- Cases & sessions
-- ---------------------------------------------------------------------------
create table if not exists public.cases (
  id uuid primary key default gen_random_uuid(),
  case_number text not null,
  title text not null,
  status public.case_status not null default 'open',
  opened_by uuid references public.users (id),
  assignee_id uuid references public.users (id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz,
  unique (case_number)
);

create index if not exists cases_status_idx on public.cases (status);
create index if not exists cases_assignee_idx on public.cases (assignee_id);

create table if not exists public.sessions (
  id uuid primary key default gen_random_uuid(),
  case_id uuid references public.cases (id) on delete set null,
  user_id uuid not null references public.users (id) on delete cascade,
  title text,
  status public.session_status not null default 'active',
  channel text not null default 'web',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists sessions_case_idx on public.sessions (case_id);
create index if not exists sessions_user_idx on public.sessions (user_id);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions (id) on delete cascade,
  role public.message_role not null,
  content text not null,
  position int not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists messages_session_position_idx on public.messages (session_id, position);
create index if not exists messages_session_created_idx on public.messages (session_id, created_at);

commit;
