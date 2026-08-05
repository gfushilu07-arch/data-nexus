-- fixture: SQLT-FIXTURE-MYSQL-CLEANUP
-- Purpose: Remove every SQLT object before rebuilding the MySQL fixture.
-- Expected: The SQLT schema contains none of the four versioned fixture tables.
-- Dialect: mysql

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS sqlt_dml_targets;
DROP TABLE IF EXISTS sqlt_orders;
DROP TABLE IF EXISTS sqlt_customers;
DROP TABLE IF EXISTS sqlt_mutations;
DROP TABLE IF EXISTS sqlt_ddl_oracle;
SET FOREIGN_KEY_CHECKS = 1;
