-- CineCircle private schema. All app tables live here.
-- It is NOT listed in config.toml [api] schemas, so the Supabase Data API never exposes it.
create schema if not exists app;
revoke all on schema app from public, anon;
grant usage on schema app to authenticated, service_role;
alter default privileges in schema app revoke all on tables from anon;
comment on schema app is 'CineCircle private schema. Never add to [api] schemas; access only through the FastAPI service.';
