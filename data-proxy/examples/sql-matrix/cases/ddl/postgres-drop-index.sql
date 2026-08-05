-- case: SQLT-DDL-035
-- Purpose: Drop a named PostgreSQL index using schema-object syntax.
-- Expected: sqlt_idx_probe disappears while sqlt_ddl_index remains unchanged.
-- Dialect: postgres

DROP INDEX sqlt_idx_probe;
