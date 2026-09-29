"""Maintenance functions for the daily schedule (spec 4.8, 7, 11.2).

The app role owns no tables, so it cannot drop a partition or read another
user's conversations. Each job it needs is a SECURITY DEFINER function that
does one bounded thing:
- drop_expired_partitions: drops audit_log months older than the retention
  period, which cannot be set below 12 months (spec 11.2). messages has no
  retention period: a user deletes their own history.
- prunable_checkpoint_threads: lists checkpoint threads whose conversation is
  deleted, gone, or idle for idle_days (spec 4.8). The app then deletes them
  with the DELETE grant it already has on the checkpoint tables.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

UPGRADE = r"""
CREATE FUNCTION drop_expired_partitions(parent text, keep_months int) RETURNS SETOF text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  cutoff timestamptz;
  part text;
BEGIN
  IF parent <> 'audit_log' THEN
    RAISE EXCEPTION USING MESSAGE = 'drop_expired_partitions: ' || parent || ' has no retention period';
  END IF;
  IF keep_months IS NULL OR keep_months < 12 THEN
    RAISE EXCEPTION USING MESSAGE = 'drop_expired_partitions: audit logs are kept at least 12 months';
  END IF;
  cutoff := now() - make_interval(months => keep_months);
  FOR part IN
    SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
    WHERE i.inhparent = parent::regclass AND c.relname ~ ('^' || parent || '_\d{4}_\d{2}$')
    ORDER BY 1
  LOOP
    -- A monthly partition goes only when its newest possible row is past the cutoff.
    IF to_date(right(part, 7), 'YYYY_MM') + interval '1 month' <= cutoff THEN
      EXECUTE 'DROP TABLE ' || quote_ident(part);
      RETURN NEXT part;
    END IF;
  END LOOP;
END
$$;
REVOKE ALL ON FUNCTION drop_expired_partitions(text, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION drop_expired_partitions(text, int) TO etheria_app;

CREATE FUNCTION prunable_checkpoint_threads(idle_days int) RETURNS SETOF text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT DISTINCT k.thread_id FROM checkpoints k
  LEFT JOIN conversations c ON c.id::text = k.thread_id
  WHERE c.id IS NULL
     OR c.deleted_at IS NOT NULL
     OR c.last_message_at < now() - make_interval(days => greatest(idle_days, 1))
$$;
REVOKE ALL ON FUNCTION prunable_checkpoint_threads(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION prunable_checkpoint_threads(int) TO etheria_app;
"""

DOWNGRADE = """
DROP FUNCTION IF EXISTS prunable_checkpoint_threads(int);
DROP FUNCTION IF EXISTS drop_expired_partitions(text, int);
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE)
