-- case: SQLT-DDL-010
-- Purpose: Rename a table while preserving its column definitions.
-- Expected: The old object disappears and sqlt_ddl_renamed retains the exact schema.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_alter RENAME TO sqlt_ddl_renamed;
