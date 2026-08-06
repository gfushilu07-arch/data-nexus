-- fixture: SQLT-FIXTURE-MYSQL-DDL-DATABASE-SETUP-IF-NOT-EXISTS-V1
-- Purpose: Ensure the CREATE DATABASE IF NOT EXISTS target is absent before an attempt.
-- Expected: No database named sqlt_ddl_boundary_if_not_exists exists.
-- Dialect: mysql

DROP DATABASE IF EXISTS sqlt_ddl_boundary_if_not_exists;
