-- case: SQLT-DDL-007
-- Purpose: Rename a column without changing its type or nullability.
-- Expected: The old name disappears and display_name retains the original definition.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_alter RENAME COLUMN probe_name TO display_name;
