-- case: SQLT-DDL-023
-- Purpose: Make a populated MySQL column not null with MODIFY COLUMN.
-- Expected: probe_value becomes not null without changing its type, default, or rows.
-- Dialect: mysql

ALTER TABLE sqlt_ddl_column
MODIFY COLUMN probe_value INTEGER NOT NULL;
