-- User email mapping (safe to run multiple times)
-- Lets Stripe Payment Links unlock Pro by matching the checkout email to a known user_id.

create table if not exists public.user_emails (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Ensure case-insensitive uniqueness on email
create unique index if not exists user_emails_email_unique
  on public.user_emails (lower(email));

alter table public.user_emails enable row level security;

drop policy if exists "user_emails_select_own" on public.user_emails;
create policy "user_emails_select_own"
  on public.user_emails
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "user_emails_insert_own" on public.user_emails;
create policy "user_emails_insert_own"
  on public.user_emails
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "user_emails_update_own" on public.user_emails;
create policy "user_emails_update_own"
  on public.user_emails
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

drop trigger if exists set_user_emails_updated_at on public.user_emails;
create trigger set_user_emails_updated_at
before update on public.user_emails
for each row execute procedure public.set_updated_at();

select pg_notify('pgrst', 'reload schema');

