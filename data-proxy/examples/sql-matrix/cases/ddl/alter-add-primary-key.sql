-- case: SQLT-DDL-015
-- Purpose: Add a primary key constraint to an existing not-null column.
-- Expected: The primary key exists on probe_id without changing the column definition.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_pk_probe PRIMARY KEY (probe_id);
