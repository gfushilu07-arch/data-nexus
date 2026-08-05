-- case: SQLT-DDL-034
-- Purpose: Drop a named MySQL index using table-qualified syntax.
-- Expected: sqlt_idx_probe disappears while sqlt_ddl_index remains unchanged.
-- Dialect: mysql

DROP INDEX sqlt_idx_probe ON sqlt_ddl_index;
