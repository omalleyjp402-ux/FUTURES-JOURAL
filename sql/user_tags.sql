-- User-defined tags for trade logging (saved dropdown suggestions)
-- Apply this in Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists public.user_tags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  unique (user_id, name)
);

alter table public.user_tags enable row level security;

drop policy if exists "user_tags_select_own" on public.user_tags;
create policy "user_tags_select_own"
  on public.user_tags
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "user_tags_insert_own" on public.user_tags;
create policy "user_tags_insert_own"
  on public.user_tags
  for insert
  to authenticated
  with check (auth.uid() = user_id);

