-- Support requests + feature suggestions
-- Paste into Supabase SQL editor (same project as your SUPABASE_URL) and Run.

create extension if not exists pgcrypto;

create table if not exists public.support_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  subject text,
  message text,
  page text,
  created_at timestamptz not null default now()
);

create table if not exists public.feature_suggestions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  title text,
  suggestion text,
  created_at timestamptz not null default now()
);

alter table public.support_requests enable row level security;
alter table public.feature_suggestions enable row level security;

-- Users can insert their own requests/suggestions.
drop policy if exists "support_insert_own" on public.support_requests;
create policy "support_insert_own"
  on public.support_requests
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "support_select_own" on public.support_requests;
create policy "support_select_own"
  on public.support_requests
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "suggest_insert_own" on public.feature_suggestions;
create policy "suggest_insert_own"
  on public.feature_suggestions
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "suggest_select_own" on public.feature_suggestions;
create policy "suggest_select_own"
  on public.feature_suggestions
  for select
  to authenticated
  using (auth.uid() = user_id);

