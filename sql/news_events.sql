-- News events table helpers
-- Goal: make bulk import easy (no need to hand-generate event_key) and prevent duplicates.

create extension if not exists pgcrypto;

-- Ensure default key generation exists (event_key = sha1(event_at|currency|title))
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='news_events' and column_name='event_key'
  ) then
    begin
      execute $q$
        alter table public.news_events
          alter column event_key
          set default encode(
            digest((event_at::text || '|' || currency || '|' || title), 'sha1'),
            'hex'
          )
      $q$;
    exception when others then
      -- ignore if table doesn't exist yet / permissions
      null;
    end;
  end if;
end $$;

-- Trigger to backfill event_key if omitted during insert/import
create or replace function public.news_events_set_key()
returns trigger
language plpgsql
as $$
begin
  if new.event_key is null or new.event_key = '' then
    new.event_key := encode(digest((new.event_at::text || '|' || new.currency || '|' || new.title), 'sha1'), 'hex');
  end if;
  return new;
end;
$$;

drop trigger if exists trg_news_events_set_key on public.news_events;
create trigger trg_news_events_set_key
before insert on public.news_events
for each row execute procedure public.news_events_set_key();

-- De-dupe existing rows (keeps the newest by created_at)
delete from public.news_events a
using public.news_events b
where a.event_key <> b.event_key
  and a.event_at = b.event_at
  and a.currency = b.currency
  and a.title = b.title
  and coalesce(a.details,'') = coalesce(b.details,'')
  and coalesce(a.raw_block,'') = coalesce(b.raw_block,'')
  and a.created_at < b.created_at;

-- Optional: prevent future duplicates (same time + currency + title + details)
do $$
begin
  if not exists (select 1 from pg_indexes where schemaname='public' and indexname='news_events_dedupe_unique') then
    execute $q$
      create unique index news_events_dedupe_unique
      on public.news_events (event_at, currency, title, coalesce(details,''), coalesce(raw_block,''))
    $q$;
  end if;
end $$;

select pg_notify('pgrst', 'reload schema');

