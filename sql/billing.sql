-- Billing + affiliate commission ledger scaffolding (Stripe webhooks will write to these).
-- Apply this in Supabase SQL editor when you're ready to integrate Stripe.

create extension if not exists pgcrypto;

create table if not exists public.stripe_events (
  id bigserial primary key,
  event_id text unique,
  event_type text,
  payload jsonb,
  received_at timestamptz not null default now()
);

create table if not exists public.affiliate_commissions (
  id uuid primary key default gen_random_uuid(),
  affiliate_user_id uuid not null references auth.users(id) on delete cascade,
  referred_user_id uuid not null references auth.users(id) on delete cascade,
  stripe_invoice_id text,
  amount_cents integer not null,
  commission_cents integer not null,
  status text not null default 'pending', -- pending | payable | paid | reversed
  created_at timestamptz not null default now()
);

alter table public.stripe_events enable row level security;
alter table public.affiliate_commissions enable row level security;

-- End users should not be able to insert/update these directly.
-- Stripe webhook / admin should use service role.

drop policy if exists "affiliate_commissions_select_affiliate" on public.affiliate_commissions;
create policy "affiliate_commissions_select_affiliate"
  on public.affiliate_commissions
  for select
  to authenticated
  using (auth.uid() = affiliate_user_id);
