-- case: SQLT-DDL-022
-- Purpose: Drop an existing integer default from a nullable column.
-- Expected: probe_value has no default without changing its type, nullability, or rows.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_column
ALTER COLUMN probe_value DROP DEFAULT;
