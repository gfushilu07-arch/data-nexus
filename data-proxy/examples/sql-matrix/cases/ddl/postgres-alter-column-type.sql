-- case: SQLT-DDL-009
-- Purpose: Expand a PostgreSQL varchar column with ALTER COLUMN TYPE syntax.
-- Expected: probe_name changes from varchar(16) to varchar(80) and remains not null.
-- Dialect: postgres

ALTER TABLE sqlt_ddl_alter ALTER COLUMN probe_name TYPE VARCHAR(80);
