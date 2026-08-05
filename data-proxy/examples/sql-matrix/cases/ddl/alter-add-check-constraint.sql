-- case: SQLT-DDL-020
-- Purpose: Add a named check constraint to an existing numeric column.
-- Expected: The check constraint requires probe_value to be positive.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_ck_probe CHECK (probe_value > 0);
