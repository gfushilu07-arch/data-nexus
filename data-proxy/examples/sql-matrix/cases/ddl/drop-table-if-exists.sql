-- case: SQLT-DDL-012
-- Purpose: Drop a nonexistent table with IF EXISTS.
-- Expected: The statement succeeds and leaves the empty DDL catalog unchanged.
-- Dialect: mysql, postgres

DROP TABLE IF EXISTS sqlt_ddl_missing;
