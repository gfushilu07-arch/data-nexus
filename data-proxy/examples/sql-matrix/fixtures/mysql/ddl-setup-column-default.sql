-- fixture: SQLT-FIXTURE-MYSQL-DDL-COLUMN-DEFAULT
-- Purpose: Create a populated MySQL table whose nullable column defaults to 7.
-- Expected: probe_value metadata and rows are ready for DROP DEFAULT.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_column (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NULL DEFAULT 7
);

INSERT INTO sqlt_ddl_column (probe_id, probe_value) VALUES (1, 10), (2, 20);
