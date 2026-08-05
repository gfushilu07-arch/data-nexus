-- fixture: SQLT-FIXTURE-POSTGRES-DDL-COLUMN-NOT-NULL
-- Purpose: Create a populated PostgreSQL table with a not-null column and no default.
-- Expected: probe_value metadata and rows are ready for DROP NOT NULL.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_column (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NOT NULL
);

INSERT INTO sqlt_ddl_column (probe_id, probe_value) VALUES (1, 10), (2, 20);
