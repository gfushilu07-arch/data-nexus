-- case: SQLT-DDL-041
-- Purpose: Attempt to drop a view that does not exist.
-- Expected: Execution fails with a stable missing-object error and leaves the catalog empty.
-- Dialect: mysql, postgres

DROP VIEW sqlt_ddl_view;
