-- Support Intelligence Platform — initial schema (Supabase / Postgres 15+)
-- Apply via: Supabase SQL Editor, `supabase db push`, or psql against your project DB.
-- Requires `auth.users` (Supabase Auth). Not for plain Docker Postgres without auth schema.

begin;

create extension if not exists pgcrypto;

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
-- Users: one application row per Supabase Auth user (extends auth.users)
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists users_email_idx on public.users (lower(email));

-- ---------------------------------------------------------------------------
-- Documents & versioning (RAG-ready: chunks hang off immutable versions)
-- ---------------------------------------------------------------------------
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.users (id) on delete cascade,
  title text not null,
  status public.document_status not null default 'draft',
  current_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists documents_owner_idx on public.documents (owner_id);
create index if not exists documents_status_idx on public.documents (status);

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
  created_at timestamptz not null default now(),
  unique (document_version_id, chunk_index)
);

create index if not exists document_chunks_version_idx on public.document_chunks (document_version_id);

comment on table public.document_chunks is
  'Text segments for retrieval. Add pgvector embedding column in a later migration.';

-- ---------------------------------------------------------------------------
-- Cases & support sessions
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

comment on column public.messages.metadata is
  'Extensible: tool_calls, langsmith_run_id, trace_id, token_usage, etc.';

-- ---------------------------------------------------------------------------
-- Sync Auth sign-ups into public.users
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, email, display_name)
  values (
    new.id,
    new.email,
    coalesce(
      new.raw_user_meta_data->>'full_name',
      new.raw_user_meta_data->>'name',
      split_part(new.email, '@', 1)
    )
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Row Level Security (baseline; service role bypasses for backend jobs)
-- ---------------------------------------------------------------------------
alter table public.users enable row level security;
alter table public.documents enable row level security;
alter table public.document_versions enable row level security;
alter table public.document_chunks enable row level security;
alter table public.cases enable row level security;
alter table public.sessions enable row level security;
alter table public.messages enable row level security;

-- Users: self read/update (rows created by trigger on sign-up)
create policy users_select_self on public.users
  for select using (auth.uid() = id);
create policy users_update_self on public.users
  for update using (auth.uid() = id)
  with check (auth.uid() = id);

-- Documents: owner
create policy documents_select on public.documents
  for select using (auth.uid() = owner_id);
create policy documents_insert on public.documents
  for insert with check (auth.uid() = owner_id);
create policy documents_update on public.documents
  for update using (auth.uid() = owner_id)
  with check (auth.uid() = owner_id);
create policy documents_delete on public.documents
  for delete using (auth.uid() = owner_id);

-- Versions: via document ownership
create policy document_versions_select on public.document_versions
  for select using (
    exists (
      select 1 from public.documents d
      where d.id = document_id and d.owner_id = auth.uid()
    )
  );
create policy document_versions_insert on public.document_versions
  for insert with check (
    exists (
      select 1 from public.documents d
      where d.id = document_id and d.owner_id = auth.uid()
    )
  );
create policy document_versions_update on public.document_versions
  for update using (
    exists (
      select 1 from public.documents d
      where d.id = document_id and d.owner_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.documents d
      where d.id = document_id and d.owner_id = auth.uid()
    )
  );
create policy document_versions_delete on public.document_versions
  for delete using (
    exists (
      select 1 from public.documents d
      where d.id = document_id and d.owner_id = auth.uid()
    )
  );

-- Chunks: via document ownership
create policy document_chunks_select on public.document_chunks
  for select using (
    exists (
      select 1
      from public.document_versions dv
      join public.documents d on d.id = dv.document_id
      where dv.id = document_chunks.document_version_id and d.owner_id = auth.uid()
    )
  );
create policy document_chunks_insert on public.document_chunks
  for insert with check (
    exists (
      select 1
      from public.document_versions dv
      join public.documents d on d.id = dv.document_id
      where dv.id = document_version_id and d.owner_id = auth.uid()
    )
  );
create policy document_chunks_update on public.document_chunks
  for update using (
    exists (
      select 1
      from public.document_versions dv
      join public.documents d on d.id = dv.document_id
      where dv.id = document_chunks.document_version_id and d.owner_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.document_versions dv
      join public.documents d on d.id = dv.document_id
      where dv.id = document_version_id and d.owner_id = auth.uid()
    )
  );
create policy document_chunks_delete on public.document_chunks
  for delete using (
    exists (
      select 1
      from public.document_versions dv
      join public.documents d on d.id = dv.document_id
      where dv.id = document_chunks.document_version_id and d.owner_id = auth.uid()
    )
  );

-- Cases: participants (extend when you add roles / teams)
create policy cases_select on public.cases
  for select using (auth.uid() = opened_by or auth.uid() = assignee_id);
create policy cases_insert on public.cases
  for insert with check (auth.uid() = opened_by);
create policy cases_update on public.cases
  for update using (auth.uid() = opened_by or auth.uid() = assignee_id)
  with check (auth.uid() = opened_by or auth.uid() = assignee_id);
create policy cases_delete on public.cases
  for delete using (auth.uid() = opened_by);

-- Sessions: owner
create policy sessions_select on public.sessions
  for select using (auth.uid() = user_id);
create policy sessions_insert on public.sessions
  for insert with check (auth.uid() = user_id);
create policy sessions_update on public.sessions
  for update using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
create policy sessions_delete on public.sessions
  for delete using (auth.uid() = user_id);

-- Messages: session owner
create policy messages_select on public.messages
  for select using (
    exists (
      select 1 from public.sessions s
      where s.id = messages.session_id and s.user_id = auth.uid()
    )
  );
create policy messages_insert on public.messages
  for insert with check (
    exists (
      select 1 from public.sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );
create policy messages_update on public.messages
  for update using (
    exists (
      select 1 from public.sessions s
      where s.id = messages.session_id and s.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );
create policy messages_delete on public.messages
  for delete using (
    exists (
      select 1 from public.sessions s
      where s.id = messages.session_id and s.user_id = auth.uid()
    )
  );

commit;
