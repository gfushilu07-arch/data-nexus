-- case: SQLT-DDL-017
-- Purpose: Remove an existing PostgreSQL named primary key constraint.
-- Expected: The primary key metadata disappears and both columns remain unchanged.
-- Dialect: postgres

ALTER TABLE sqlt_ddl_constraint DROP CONSTRAINT sqlt_pk_probe;
