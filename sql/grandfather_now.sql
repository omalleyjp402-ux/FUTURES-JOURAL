-- Run ONCE right before enabling PAYWALL_ENABLED=true in Streamlit secrets.
-- This will grandfather everyone who already has an account at the moment you run it.

insert into public.entitlements (user_id, plan, trade_limit)
select id, 'grandfathered', null
from auth.users
on conflict (user_id) do update
set plan = excluded.plan,
    trade_limit = excluded.trade_limit,
    updated_at = now();

