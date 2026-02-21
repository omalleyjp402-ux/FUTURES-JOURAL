-- Affiliate / referral tracking (Stripe commission is handled via webhook later)
-- Apply this in Supabase SQL editor.

create table if not exists public.affiliate_codes (
  code text primary key,
  affiliate_user_id uuid not null references auth.users(id) on delete cascade,
  commission_percent numeric not null default 20,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.referrals (
  referred_user_id uuid primary key references auth.users(id) on delete cascade,
  affiliate_user_id uuid not null references auth.users(id) on delete cascade,
  code text not null references public.affiliate_codes(code) on delete restrict,
  created_at timestamptz not null default now()
);

alter table public.affiliate_codes enable row level security;
alter table public.referrals enable row level security;

-- Anyone authenticated can resolve a code -> affiliate_user_id (needed at signup/login).
drop policy if exists "affiliate_codes_select_authed" on public.affiliate_codes;
create policy "affiliate_codes_select_authed"
  on public.affiliate_codes
  for select
  to authenticated
  using (is_active = true);

-- Affiliates can view their own codes.
drop policy if exists "affiliate_codes_manage_own" on public.affiliate_codes;
create policy "affiliate_codes_manage_own"
  on public.affiliate_codes
  for all
  to authenticated
  using (auth.uid() = affiliate_user_id)
  with check (auth.uid() = affiliate_user_id);

-- Users can see their own referral row (so the app can show "referred by").
drop policy if exists "referrals_select_own" on public.referrals;
create policy "referrals_select_own"
  on public.referrals
  for select
  to authenticated
  using (auth.uid() = referred_user_id);

-- Affiliates can see referrals attributed to them.
drop policy if exists "referrals_select_affiliate" on public.referrals;
create policy "referrals_select_affiliate"
  on public.referrals
  for select
  to authenticated
  using (auth.uid() = affiliate_user_id);

-- Users can insert a referral row for themselves (one-time) when they arrive with ?ref=CODE.
-- Prevent self-referral.
drop policy if exists "referrals_insert_self" on public.referrals;
create policy "referrals_insert_self"
  on public.referrals
  for insert
  to authenticated
  with check (
    auth.uid() = referred_user_id
    and affiliate_user_id <> referred_user_id
  );

