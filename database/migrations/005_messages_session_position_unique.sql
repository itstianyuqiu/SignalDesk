-- Enforce stable per-session transcript ordering at the database layer.
-- Apply after 001_initial_schema.sql (and 004_cases_workflow.sql when used).

begin;

do $$
begin
  if exists (
    select 1
    from public.messages
    group by session_id, position
    having count(*) > 1
  ) then
    raise exception
      'Cannot add unique message position constraint: duplicate (session_id, position) rows already exist.';
  end if;
end
$$;

drop index if exists public.messages_session_position_idx;

create unique index if not exists messages_session_position_uidx
  on public.messages (session_id, position);

commit;
