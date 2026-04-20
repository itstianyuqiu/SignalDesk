-- Cases workflow: summary, priority, category, origin session; action items; document links.
-- Apply after 001_initial_schema.sql
--
-- RLS policies below use auth.uid() (Supabase). Plain Postgres / local Docker has no auth schema
-- until this stub runs. On real Supabase, auth.uid() already exists — we do NOT replace it.

begin;

do $stub$
begin
  if not exists (
    select 1
    from pg_proc p
    join pg_namespace n on p.pronamespace = n.oid
    where n.nspname = 'auth' and p.proname = 'uid'
  ) then
    create schema if not exists auth;
    create function auth.uid() returns uuid
    language sql
    stable
    as $fn$ select null::uuid $fn$;
  end if;
end
$stub$;

-- Priority for cases (separate from case_status workflow)
do $$ begin
  create type public.case_priority as enum ('low', 'medium', 'high', 'critical');
exception when duplicate_object then null;
end $$;

alter table public.cases
  add column if not exists summary text not null default '',
  add column if not exists priority public.case_priority not null default 'medium',
  add column if not exists category text,
  add column if not exists created_from_session_id uuid references public.sessions (id) on delete set null;

create unique index if not exists cases_created_from_session_uidx
  on public.cases (created_from_session_id)
  where created_from_session_id is not null;

create index if not exists cases_opened_by_idx on public.cases (opened_by);

-- ---------------------------------------------------------------------------
-- Case action items
-- ---------------------------------------------------------------------------
create table if not exists public.case_action_items (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  title text not null,
  status text not null check (status in ('todo', 'in_progress', 'done')),
  owner text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists case_action_items_case_idx on public.case_action_items (case_id);

-- ---------------------------------------------------------------------------
-- Case ↔ document links (knowledge cited during investigation)
-- ---------------------------------------------------------------------------
create table if not exists public.case_documents (
  case_id uuid not null references public.cases (id) on delete cascade,
  document_id uuid not null references public.documents (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (case_id, document_id)
);

-- ---------------------------------------------------------------------------
-- RLS (same visibility as parent case)
-- ---------------------------------------------------------------------------
alter table public.case_action_items enable row level security;
alter table public.case_documents enable row level security;

create policy case_action_items_select on public.case_action_items
  for select using (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );
create policy case_action_items_insert on public.case_action_items
  for insert with check (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );
create policy case_action_items_update on public.case_action_items
  for update using (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  )
  with check (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );
create policy case_action_items_delete on public.case_action_items
  for delete using (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );

create policy case_documents_select on public.case_documents
  for select using (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );
create policy case_documents_insert on public.case_documents
  for insert with check (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );
create policy case_documents_delete on public.case_documents
  for delete using (
    exists (
      select 1 from public.cases c
      where c.id = case_id
        and (c.opened_by = auth.uid() or c.assignee_id = auth.uid())
    )
  );

commit;
