-- Weekly journal entries (safe to run multiple times)
-- Stores 1 entry per user per week (week_start = Monday).

create table if not exists public.weekly_journal_entries (
  user_id uuid references auth.users(id) on delete cascade not null,
  week_start date not null,
  did_well text,
  needs_improved text,
  patterns text,
  focus_next text,
  other_notes text,
  improvement_percent numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, week_start)
);

-- Forward-compatible: add new columns safely if the table already exists
alter table public.weekly_journal_entries
  add column if not exists other_notes text;

alter table public.weekly_journal_entries enable row level security;

drop policy if exists "weekly_journal_select_own" on public.weekly_journal_entries;
create policy "weekly_journal_select_own"
  on public.weekly_journal_entries
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "weekly_journal_insert_own" on public.weekly_journal_entries;
create policy "weekly_journal_insert_own"
  on public.weekly_journal_entries
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "weekly_journal_update_own" on public.weekly_journal_entries;
create policy "weekly_journal_update_own"
  on public.weekly_journal_entries
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- updated_at helper (shared across tables, safe to re-create)
create or replace function public.set_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_weekly_journal_updated_at on public.weekly_journal_entries;
create trigger set_weekly_journal_updated_at
before update on public.weekly_journal_entries
for each row execute procedure public.set_updated_at();

select pg_notify('pgrst', 'reload schema');
