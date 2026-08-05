-- case: SQLT-DDL-021
-- Purpose: Set an integer default on an existing nullable column.
-- Expected: probe_value has default 7 without changing its type, nullability, or rows.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_column
ALTER COLUMN probe_value SET DEFAULT 7;
