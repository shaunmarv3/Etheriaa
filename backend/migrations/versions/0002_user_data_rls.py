"""User data tables with row-level security, and public reference tables (spec 7).

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  title text,
  triage_level text CHECK (triage_level IN ('RED', 'YELLOW', 'GREEN')),
  started_at timestamptz NOT NULL DEFAULT now(),
  last_message_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  -- Target of composite FKs: a child row must belong to its parent's user.
  UNIQUE (id, user_id)
);
CREATE INDEX conversations_user_recent_idx
  ON conversations (user_id, last_message_at DESC) WHERE deleted_at IS NULL;

CREATE TABLE messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  conversation_id uuid NOT NULL,
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,
  intent text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  superseded_at timestamptz,
  PRIMARY KEY (id, created_at),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
) PARTITION BY RANGE (created_at);
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);
CREATE TABLE messages_default PARTITION OF messages DEFAULT;
REVOKE ALL ON messages_default FROM etheria_app;
SELECT ensure_monthly_partitions('messages', 3);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  filename text NOT NULL,
  mime_type text NOT NULL CHECK (mime_type IN ('application/pdf', 'image/png', 'image/jpeg')),
  storage_key text NOT NULL UNIQUE,
  sha256 text NOT NULL,
  size_bytes integer NOT NULL CHECK (size_bytes > 0),
  page_count integer,
  doc_type text CHECK (doc_type IN ('lab_report', 'prescription', 'discharge_summary', 'imaging_report', 'other')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed')),
  report_date date,
  lab_name text,
  summary text,
  extracted jsonb,
  extraction_stats jsonb,
  error_code text,
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  UNIQUE (id, user_id),
  UNIQUE (user_id, sha256)
);

CREATE TABLE document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL,
  user_id uuid NOT NULL,
  chunk_index integer NOT NULL,
  page integer,
  source_kind text NOT NULL CHECK (source_kind IN ('text_layer', 'ocr')),
  content text NOT NULL,
  embedding vector(1024) NOT NULL,
  -- 'simple' keeps tokens such as HbA1c intact (spec 5.7).
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  UNIQUE (document_id, chunk_index),
  FOREIGN KEY (document_id, user_id) REFERENCES documents (id, user_id) ON DELETE CASCADE
);
CREATE INDEX document_chunks_embedding_idx ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX document_chunks_tsv_idx ON document_chunks USING gin (tsv);
CREATE INDEX document_chunks_user_idx ON document_chunks (user_id);

CREATE TABLE lab_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  document_id uuid NOT NULL,
  test_name text NOT NULL,
  value_text text NOT NULL,
  value_numeric numeric,
  unit text,
  ref_range_text text,
  ref_low numeric,
  ref_high numeric,
  flag text NOT NULL CHECK (flag IN ('low', 'normal', 'high', 'unknown')),
  report_date date,
  page integer,
  FOREIGN KEY (document_id, user_id) REFERENCES documents (id, user_id) ON DELETE CASCADE
);
CREATE INDEX lab_results_user_test_idx ON lab_results (user_id, lower(test_name));

CREATE TABLE medications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  document_id uuid,
  name_raw text NOT NULL,
  ingredients text[] NOT NULL DEFAULT '{}',
  dose text,
  frequency text,
  duration text,
  source text NOT NULL CHECK (source IN ('prescription', 'discharge_summary')),
  report_date date,
  FOREIGN KEY (document_id, user_id) REFERENCES documents (id, user_id) ON DELETE CASCADE
);
CREATE INDEX medications_user_idx ON medications (user_id);

-- Public reference data (spec 6.2): no RLS, read-only to the app.
CREATE TABLE medicine_brands (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name text NOT NULL,
  manufacturer text,
  type text,
  pack_size_label text,
  composition1 text,
  composition2 text,
  ingredients text[] NOT NULL DEFAULT '{}',
  is_discontinued boolean NOT NULL DEFAULT false
);
CREATE INDEX medicine_brands_name_trgm_idx ON medicine_brands USING gin (name gin_trgm_ops);
CREATE INDEX medicine_brands_name_lower_idx ON medicine_brands (lower(name));

CREATE TABLE drug_synonyms (
  alias citext PRIMARY KEY,
  canonical text NOT NULL
);
REVOKE INSERT, UPDATE, DELETE ON medicine_brands, drug_synonyms FROM etheria_app;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['conversations', 'messages', 'documents', 'document_chunks', 'lab_results', 'medications'] LOOP
    EXECUTE 'ALTER TABLE ' || quote_ident(t) || ' ENABLE ROW LEVEL SECURITY';
    EXECUTE 'CREATE POLICY ' || quote_ident(t || '_owner') || ' ON ' || quote_ident(t)
         || ' USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user())';
  END LOOP;
END
$$;

-- Readiness check (spec 7): a row in a default partition means a monthly partition is missing.
CREATE FUNCTION default_partitions_empty() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT NOT EXISTS (SELECT 1 FROM messages_default) AND NOT EXISTS (SELECT 1 FROM audit_log_default) $$;
REVOKE ALL ON FUNCTION default_partitions_empty() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION default_partitions_empty() TO etheria_app;
"""

DOWNGRADE = """
DROP FUNCTION IF EXISTS default_partitions_empty();
DROP TABLE IF EXISTS medications, lab_results, document_chunks, documents, messages,
  conversations, drug_synonyms, medicine_brands CASCADE;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE)
