-- case: SQLT-DDL-029
-- Purpose: Add a named positive-value check over an existing non-positive value.
-- Expected: The statement fails without creating the check or changing table data.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_ck_conflict CHECK (probe_value > 0);
