-- case: SQLT-DDL-031
-- Purpose: Make a PostgreSQL column not null while it contains an existing NULL.
-- Expected: The statement fails without changing column metadata or table data.
-- Dialect: postgres

ALTER TABLE sqlt_ddl_column
ALTER COLUMN probe_value SET NOT NULL;
