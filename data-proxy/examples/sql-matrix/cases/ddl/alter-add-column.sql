-- case: SQLT-DDL-005
-- Purpose: Add a nullable note column to an existing table.
-- Expected: The new column appears last with the exact varchar length and nullability.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_alter ADD COLUMN probe_note VARCHAR(32);
