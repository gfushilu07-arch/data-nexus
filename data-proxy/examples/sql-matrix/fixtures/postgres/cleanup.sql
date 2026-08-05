-- fixture: SQLT-FIXTURE-POSTGRES-CLEANUP
-- Purpose: Remove every SQLT object before rebuilding the PostgreSQL fixture.
-- Expected: The public schema contains none of the four versioned fixture tables.
-- Dialect: postgres

DROP TABLE IF EXISTS sqlt_dml_targets;
DROP TABLE IF EXISTS sqlt_orders;
DROP TABLE IF EXISTS sqlt_customers;
DROP TABLE IF EXISTS sqlt_mutations;
DROP TABLE IF EXISTS sqlt_ddl_oracle;
