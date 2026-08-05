-- case: SQLT-DDL-024
-- Purpose: Make a populated PostgreSQL column not null with SET NOT NULL.
-- Expected: probe_value becomes not null without changing its type, default, or rows.
-- Dialect: postgres

ALTER TABLE sqlt_ddl_column
ALTER COLUMN probe_value SET NOT NULL;
