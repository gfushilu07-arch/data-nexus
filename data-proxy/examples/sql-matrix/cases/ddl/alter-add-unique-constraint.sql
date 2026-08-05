-- case: SQLT-DDL-018
-- Purpose: Add a named unique constraint to an existing column.
-- Expected: The unique constraint and its implicit unique index cover probe_name.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_uq_probe UNIQUE (probe_name);
