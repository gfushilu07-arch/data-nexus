-- fixture: SQLT-FIXTURE-POSTGRES-DDL-IF-NOT-EXISTS
-- Purpose: Create the PostgreSQL baseline table used by the idempotent CREATE case.
-- Expected: The baseline table has two deterministic non-null columns.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_if_not_exists (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
