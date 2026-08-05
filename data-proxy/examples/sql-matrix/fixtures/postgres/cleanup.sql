-- fixture: SQLT-FIXTURE-POSTGRES-CLEANUP
-- Purpose: Remove every SQLT object before rebuilding the PostgreSQL fixture.
-- Expected: The public schema contains none of the versioned fixture and DDL probe tables.
-- Dialect: postgres

DROP TABLE IF EXISTS sqlt_dml_targets;
DROP TABLE IF EXISTS sqlt_orders;
DROP TABLE IF EXISTS sqlt_customers;
DROP TABLE IF EXISTS sqlt_mutations;
DROP TABLE IF EXISTS sqlt_ddl_oracle;
DROP TABLE IF EXISTS sqlt_ddl_probe;
DROP TABLE IF EXISTS sqlt_ddl_create;
DROP TABLE IF EXISTS sqlt_ddl_if_not_exists;
DROP TABLE IF EXISTS sqlt_ddl_duplicate;
DROP TABLE IF EXISTS sqlt_ddl_alter;
DROP TABLE IF EXISTS sqlt_ddl_renamed;
DROP TABLE IF EXISTS sqlt_ddl_truncate;
DROP TABLE IF EXISTS sqlt_ddl_missing;
DROP TABLE IF EXISTS sqlt_ddl_temp;
