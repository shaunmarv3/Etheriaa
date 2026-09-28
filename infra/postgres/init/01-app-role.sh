#!/bin/bash
# Runs once, on first initialisation of the data volume.
# etheria_app is the least-privilege role the application connects as:
# it does not own the tables, so row-level security applies to it (spec 7).
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE ROLE etheria_app LOGIN PASSWORD '${ETHERIA_APP_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO etheria_app;
EOSQL
