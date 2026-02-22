-- User-defined strategies (templates)
-- Apply this in Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists public.strategies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

alter table public.strategies enable row level security;

drop policy if exists "strategies_select_own" on public.strategies;
create policy "strategies_select_own"
  on public.strategies
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "strategies_insert_own" on public.strategies;
create policy "strategies_insert_own"
  on public.strategies
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "strategies_update_own" on public.strategies;
create policy "strategies_update_own"
  on public.strategies
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

drop trigger if exists set_strategies_updated_at on public.strategies;
create trigger set_strategies_updated_at
before update on public.strategies
for each row execute procedure public.set_updated_at();
