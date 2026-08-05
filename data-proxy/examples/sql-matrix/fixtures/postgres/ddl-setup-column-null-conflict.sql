-- fixture: SQLT-FIXTURE-POSTGRES-DDL-COLUMN-NULL-CONFLICT
-- Purpose: Create a PostgreSQL nullable column containing an existing NULL value.
-- Expected: Making probe_value not null is rejected.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_column (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NULL
);

INSERT INTO sqlt_ddl_column (probe_id, probe_value) VALUES (1, NULL), (2, 20);
