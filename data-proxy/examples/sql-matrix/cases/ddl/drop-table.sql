-- case: SQLT-DDL-011
-- Purpose: Drop an existing table from the active schema.
-- Expected: The table and all of its column metadata disappear.
-- Dialect: mysql, postgres

DROP TABLE sqlt_ddl_alter;
