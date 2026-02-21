-- Daily journal entries (one per user per day)
-- Apply this in Supabase SQL editor.

create table if not exists public.journal_entries (
  user_id uuid not null references auth.users(id) on delete cascade,
  entry_date date not null,
  content text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, entry_date)
);

alter table public.journal_entries enable row level security;

drop policy if exists "journal_select_own" on public.journal_entries;
create policy "journal_select_own"
  on public.journal_entries
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "journal_insert_own" on public.journal_entries;
create policy "journal_insert_own"
  on public.journal_entries
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "journal_update_own" on public.journal_entries;
create policy "journal_update_own"
  on public.journal_entries
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_journal_updated_at on public.journal_entries;
create trigger set_journal_updated_at
before update on public.journal_entries
for each row execute procedure public.set_updated_at();

