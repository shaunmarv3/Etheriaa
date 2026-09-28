"""Foundation: extensions, app-role grants, auth tables, partitioned audit log.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'etheria_app') THEN
    RAISE EXCEPTION 'role etheria_app is missing: infra/postgres/init/01-app-role.sh creates it';
  END IF;
END
$$;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

-- Every table the owner creates from here on is usable by the app role.
GRANT USAGE ON SCHEMA public TO etheria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO etheria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO etheria_app;

-- The user a request runs as (spec 7). NULL when unset, so RLS returns no rows.
CREATE FUNCTION app_current_user() RETURNS uuid
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext NOT NULL UNIQUE,
  password_hash text NOT NULL,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  family_id uuid NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  replaced_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  user_agent text
);
CREATE INDEX refresh_tokens_family_idx ON refresh_tokens (family_id);
CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);

CREATE TABLE audit_log (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  user_ref text,
  action text NOT NULL,
  resource_type text,
  resource_id text,
  ip inet,
  user_agent text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX audit_log_user_ref_idx ON audit_log (user_ref, created_at);
CREATE TABLE audit_log_default PARTITION OF audit_log DEFAULT;
REVOKE ALL ON audit_log_default FROM etheria_app;
-- Kept for a year (spec 11.2): the app may add and pseudonymise rows, never delete them.
REVOKE DELETE ON audit_log FROM etheria_app;

CREATE FUNCTION ensure_monthly_partitions(parent text, months_ahead int) RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  first_month date := date_trunc('month', now())::date;
  month_start date;
  part text;
  made int := 0;
BEGIN
  IF parent NOT IN ('messages', 'audit_log') THEN
    RAISE EXCEPTION USING MESSAGE = 'ensure_monthly_partitions: ' || parent || ' is not managed';
  END IF;
  FOR i IN 0..months_ahead LOOP
    month_start := (first_month + make_interval(months => i))::date;
    part := parent || '_' || to_char(month_start, 'YYYY_MM');
    IF to_regclass(part) IS NULL THEN
      EXECUTE 'CREATE TABLE ' || quote_ident(part) || ' PARTITION OF ' || quote_ident(parent)
           || ' FOR VALUES FROM (' || quote_literal(month_start) || ') TO ('
           || quote_literal((month_start + interval '1 month')::date) || ')';
      -- Reading a partition directly would bypass the parent's RLS policy.
      EXECUTE 'REVOKE ALL ON ' || quote_ident(part) || ' FROM etheria_app';
      made := made + 1;
    END IF;
  END LOOP;
  RETURN made;
END
$$;
REVOKE ALL ON FUNCTION ensure_monthly_partitions(text, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ensure_monthly_partitions(text, int) TO etheria_app;

SELECT ensure_monthly_partitions('audit_log', 3);
"""

DOWNGRADE = """
DROP FUNCTION IF EXISTS ensure_monthly_partitions(text, int);
DROP TABLE IF EXISTS audit_log, refresh_tokens, users CASCADE;
DROP FUNCTION IF EXISTS app_current_user();
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM etheria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM etheria_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE)
