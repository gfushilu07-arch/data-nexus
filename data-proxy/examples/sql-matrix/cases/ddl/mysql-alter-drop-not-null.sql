-- case: SQLT-DDL-025
-- Purpose: Make a MySQL not-null column nullable with MODIFY COLUMN.
-- Expected: probe_value becomes nullable without changing its type, default, or rows.
-- Dialect: mysql

ALTER TABLE sqlt_ddl_column
MODIFY COLUMN probe_value INTEGER NULL;
