-- case: SQLT-DDL-006
-- Purpose: Drop an existing note column from a table.
-- Expected: The note column disappears while the remaining columns preserve their order.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_alter DROP COLUMN probe_note;
