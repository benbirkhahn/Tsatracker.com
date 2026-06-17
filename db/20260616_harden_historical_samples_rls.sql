begin;

alter table public.historical_samples enable row level security;

revoke all privileges on table public.historical_samples from anon, authenticated;
revoke all privileges on all sequences in schema public from anon, authenticated;

revoke all privileges on table public.historical_samples from service_role;
grant select, insert on table public.historical_samples to service_role;
grant usage, select on all sequences in schema public to service_role;

drop policy if exists "service_role can read historical samples" on public.historical_samples;
create policy "service_role can read historical samples"
on public.historical_samples
for select
to service_role
using (true);

drop policy if exists "service_role can insert historical samples" on public.historical_samples;
create policy "service_role can insert historical samples"
on public.historical_samples
for insert
to service_role
with check (true);

revoke execute on function public.rls_auto_enable() from public;
revoke execute on function public.rls_auto_enable() from anon, authenticated;

commit;
