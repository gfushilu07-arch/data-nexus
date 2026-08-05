-- case: SQLT-DDL-008
-- Purpose: Expand a MySQL varchar column with MODIFY COLUMN syntax.
-- Expected: probe_name changes from varchar(16) to varchar(80) and remains not null.
-- Dialect: mysql

ALTER TABLE sqlt_ddl_alter MODIFY COLUMN probe_name VARCHAR(80) NOT NULL;
