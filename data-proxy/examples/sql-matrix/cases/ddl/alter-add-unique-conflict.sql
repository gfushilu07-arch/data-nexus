-- case: SQLT-DDL-027
-- Purpose: Add a named unique constraint over existing duplicate values.
-- Expected: The statement fails without creating a constraint or implicit index.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_uq_conflict UNIQUE (probe_value);
