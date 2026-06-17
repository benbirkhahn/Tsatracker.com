-- Destructive cleanup for Supabase free-plan quota recovery.
-- This preserves older samples as compact hourly aggregates, removes raw
-- historical_samples older than 21 days, then rewrites the table so Postgres
-- returns the deleted space to the database size metric.
--
-- Run during a low-traffic window. VACUUM FULL takes an exclusive table lock.

create table if not exists public.historical_samples_hourly (
    hour_bucket timestamp with time zone not null,
    airport_code text not null,
    checkpoint text not null,
    lane_type text not null default 'STANDARD',
    source text not null default '',
    wait_sum double precision not null,
    sample_count integer not null,
    min_wait_minutes real not null,
    max_wait_minutes real not null,
    first_captured_at timestamp with time zone not null,
    last_captured_at timestamp with time zone not null,
    refreshed_at timestamp with time zone not null default now(),
    primary key (hour_bucket, airport_code, checkpoint, lane_type, source)
);

alter table public.historical_samples_hourly enable row level security;

revoke all privileges on table public.historical_samples_hourly from anon, authenticated;
grant select, insert, update on table public.historical_samples_hourly to service_role;

drop policy if exists "service_role can read historical sample hourly aggregates" on public.historical_samples_hourly;
create policy "service_role can read historical sample hourly aggregates"
on public.historical_samples_hourly
for select
to service_role
using (true);

drop policy if exists "service_role can upsert historical sample hourly aggregates" on public.historical_samples_hourly;
create policy "service_role can upsert historical sample hourly aggregates"
on public.historical_samples_hourly
for insert
to service_role
with check (true);

drop policy if exists "service_role can update historical sample hourly aggregates" on public.historical_samples_hourly;
create policy "service_role can update historical sample hourly aggregates"
on public.historical_samples_hourly
for update
to service_role
using (true)
with check (true);

create index if not exists idx_historical_samples_hourly_airport_hour
on public.historical_samples_hourly (airport_code, hour_bucket);

insert into public.historical_samples_hourly (
    hour_bucket,
    airport_code,
    checkpoint,
    lane_type,
    source,
    wait_sum,
    sample_count,
    min_wait_minutes,
    max_wait_minutes,
    first_captured_at,
    last_captured_at,
    refreshed_at
)
select
    date_trunc('hour', captured_at) as hour_bucket,
    airport_code,
    checkpoint,
    coalesce(lane_type, 'STANDARD') as lane_type,
    coalesce(source, '') as source,
    sum(wait_minutes)::double precision as wait_sum,
    count(*)::integer as sample_count,
    min(wait_minutes)::real as min_wait_minutes,
    max(wait_minutes)::real as max_wait_minutes,
    min(captured_at) as first_captured_at,
    max(captured_at) as last_captured_at,
    now() as refreshed_at
from public.historical_samples
where captured_at < now() - interval '21 days'
group by 1, 2, 3, 4, 5
on conflict (hour_bucket, airport_code, checkpoint, lane_type, source)
do update set
    wait_sum = excluded.wait_sum,
    sample_count = excluded.sample_count,
    min_wait_minutes = excluded.min_wait_minutes,
    max_wait_minutes = excluded.max_wait_minutes,
    first_captured_at = excluded.first_captured_at,
    last_captured_at = excluded.last_captured_at,
    refreshed_at = excluded.refreshed_at;

delete from public.historical_samples
where captured_at < now() - interval '21 days';

vacuum full analyze public.historical_samples;
