-- fixture: SQLT-FIXTURE-MYSQL-DDL-DATABASE-SETUP-CREATE-V1
-- Purpose: Ensure the CREATE DATABASE target is absent before a restricted-account attempt.
-- Expected: No database named sqlt_ddl_boundary_create exists.
-- Dialect: mysql

DROP DATABASE IF EXISTS sqlt_ddl_boundary_create;
