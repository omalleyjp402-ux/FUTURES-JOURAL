-- Billing / affiliate promo configuration (safe to run multiple times)
-- This table lets us run a launch promo where affiliate commission is higher
-- for a fixed window, then automatically drops to the default rate.

create table if not exists public.billing_config (
  id integer primary key,
  affiliate_promo_start_at timestamptz,
  affiliate_promo_end_at timestamptz,
  promo_commission_percent numeric not null default 30,
  default_commission_percent numeric not null default 20,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Singleton row.
insert into public.billing_config (id)
values (1)
on conflict (id) do nothing;

alter table public.billing_config enable row level security;

drop policy if exists "billing_config_select_authed" on public.billing_config;
create policy "billing_config_select_authed"
  on public.billing_config
  for select
  to authenticated
  using (true);

select pg_notify('pgrst', 'reload schema');

