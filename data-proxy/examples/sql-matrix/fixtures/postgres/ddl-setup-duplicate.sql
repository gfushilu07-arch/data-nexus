-- fixture: SQLT-FIXTURE-POSTGRES-DDL-DUPLICATE
-- Purpose: Create the PostgreSQL baseline table used by the duplicate CREATE error case.
-- Expected: The baseline table exists before the tested CREATE statement runs.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_duplicate (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
