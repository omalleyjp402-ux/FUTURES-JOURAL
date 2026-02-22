-- Public waitlist + public contact messages (unauthenticated inserts)
-- Paste into Supabase SQL editor (same project as your SUPABASE_URL) and Run.

create extension if not exists pgcrypto;

create table if not exists public.waitlist_emails (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  source text,
  created_at timestamptz not null default now(),
  unique (email)
);

create table if not exists public.public_contact_messages (
  id uuid primary key default gen_random_uuid(),
  email text,
  subject text,
  message text,
  page text,
  created_at timestamptz not null default now()
);

alter table public.waitlist_emails enable row level security;
alter table public.public_contact_messages enable row level security;

-- Allow anonymous inserts (public landing page).
drop policy if exists "waitlist_insert_anon" on public.waitlist_emails;
create policy "waitlist_insert_anon"
  on public.waitlist_emails
  for insert
  to anon
  with check (true);

drop policy if exists "contact_insert_anon" on public.public_contact_messages;
create policy "contact_insert_anon"
  on public.public_contact_messages
  for insert
  to anon
  with check (true);

