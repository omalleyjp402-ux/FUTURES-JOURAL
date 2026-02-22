-- Stripe webhook prerequisites (safe to run multiple times)
-- Paste into Supabase SQL Editor BEFORE deploying the stripe-webhook Edge Function.

-- Add Stripe/subscription columns to entitlements (webhook writes these using service role)
alter table public.entitlements
  add column if not exists stripe_customer_id text,
  add column if not exists stripe_subscription_id text,
  add column if not exists subscription_status text,
  add column if not exists current_period_end timestamptz;

create index if not exists entitlements_stripe_subscription_id_idx
  on public.entitlements (stripe_subscription_id);

-- Make affiliate commissions idempotent + hold commissions for refund window
alter table public.affiliate_commissions
  add column if not exists available_at timestamptz not null default (now() + interval '1 day'),
  add column if not exists currency text not null default 'usd',
  add column if not exists stripe_customer_id text;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'affiliate_commissions_invoice_unique'
  ) then
    alter table public.affiliate_commissions
      add constraint affiliate_commissions_invoice_unique
      unique (affiliate_user_id, stripe_invoice_id);
  end if;
end $$;

