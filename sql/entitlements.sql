-- Entitlements for pricing / trade limits
-- Apply this in Supabase SQL editor before enabling PAYWALL_ENABLED.

create table if not exists public.entitlements (
  user_id uuid primary key references auth.users(id) on delete cascade,
  plan text not null default 'free', -- free | pro | grandfathered | lifetime
  trade_limit integer,              -- NULL means unlimited
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.entitlements enable row level security;

-- Users can read their own entitlement.
drop policy if exists "entitlements_select_own" on public.entitlements;
create policy "entitlements_select_own"
  on public.entitlements
  for select
  using (auth.uid() = user_id);

-- Users can create their own entitlement row (free only).
drop policy if exists "entitlements_insert_free_only" on public.entitlements;
create policy "entitlements_insert_free_only"
  on public.entitlements
  for insert
  with check (
    auth.uid() = user_id
    and plan = 'free'
    and trade_limit = 15
  );

-- No UPDATE policy on purpose: users can't self-upgrade or change limits.
-- Upgrades/downgrades should be done via service role (Stripe webhook / admin tooling).

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_entitlements_updated_at on public.entitlements;
create trigger set_entitlements_updated_at
before update on public.entitlements
for each row execute procedure public.set_updated_at();

-- Grandfathering example (run once at launch):
-- Replace the timestamp with your launch cutoff.
--
-- insert into public.entitlements (user_id, plan, trade_limit)
-- select id, 'grandfathered', null
-- from auth.users
-- where created_at < '2026-03-01T00:00:00Z'
-- on conflict (user_id) do update
-- set plan = excluded.plan, trade_limit = excluded.trade_limit, updated_at = now();

