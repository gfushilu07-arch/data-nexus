-- case: SQLT-DDL-030
-- Purpose: Make a MySQL column not null while it contains an existing NULL.
-- Expected: The statement fails without changing column metadata or table data.
-- Dialect: mysql

ALTER TABLE sqlt_ddl_column
MODIFY COLUMN probe_value INTEGER NOT NULL;
