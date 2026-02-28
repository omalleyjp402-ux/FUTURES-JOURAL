-- Update existing free entitlements to the new 5-trade limit.
-- Safe to run multiple times.

update public.entitlements
set trade_limit = 5,
    updated_at = now()
where plan = 'free'
  and (trade_limit is null or trade_limit <> 5);

select plan, trade_limit, count(*) as users
from public.entitlements
group by plan, trade_limit
order by plan, trade_limit;

