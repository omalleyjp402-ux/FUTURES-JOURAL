-- Stripe Connect affiliate payout scaffolding (safe to run multiple times)
-- Paste into Supabase SQL Editor when you're ready to prep automatic payouts.
--
-- Notes:
-- - The Streamlit app does NOT enable payouts automatically.
-- - The `affiliate-payouts` Edge Function will look for `affiliate_payout_accounts.status='active'`
--   and will create Stripe transfers for commissions once `available_at` has passed.

create extension if not exists pgcrypto;

create table if not exists public.affiliate_payout_accounts (
  affiliate_user_id uuid primary key references auth.users(id) on delete cascade,
  stripe_account_id text not null, -- acct_...
  status text not null default 'pending', -- pending | active | paused
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.affiliate_payout_accounts enable row level security;

drop policy if exists "affiliate_payout_accounts_select_own" on public.affiliate_payout_accounts;
create policy "affiliate_payout_accounts_select_own"
  on public.affiliate_payout_accounts
  for select
  to authenticated
  using (auth.uid() = affiliate_user_id);

-- No insert/update policies: should be managed by admin/service role.

-- Add transfer fields to affiliate_commissions if missing
alter table public.affiliate_commissions
  add column if not exists stripe_transfer_id text,
  add column if not exists paid_at timestamptz;

create index if not exists affiliate_commissions_payable_idx
  on public.affiliate_commissions (status, available_at)
  where stripe_transfer_id is null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'affiliate_commissions_transfer_unique'
  ) then
    alter table public.affiliate_commissions
      add constraint affiliate_commissions_transfer_unique
      unique (stripe_transfer_id);
  end if;
end $$;

-- Refresh schema cache
select pg_notify('pgrst', 'reload schema');

