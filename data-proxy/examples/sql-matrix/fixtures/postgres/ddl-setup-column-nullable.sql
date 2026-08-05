-- fixture: SQLT-FIXTURE-POSTGRES-DDL-COLUMN-NULLABLE
-- Purpose: Create a populated PostgreSQL table with a nullable column and no default.
-- Expected: probe_value metadata and rows are ready for SET DEFAULT or SET NOT NULL.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_column (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NULL
);

INSERT INTO sqlt_ddl_column (probe_id, probe_value) VALUES (1, 10), (2, 20);
