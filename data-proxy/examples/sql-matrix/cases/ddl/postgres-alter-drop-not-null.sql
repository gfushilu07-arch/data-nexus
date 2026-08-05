-- case: SQLT-DDL-026
-- Purpose: Make a PostgreSQL not-null column nullable with DROP NOT NULL.
-- Expected: probe_value becomes nullable without changing its type, default, or rows.
-- Dialect: postgres

ALTER TABLE sqlt_ddl_column
ALTER COLUMN probe_value DROP NOT NULL;
