-- oracle: SQLT-ORACLE-MYSQL-DDL-DATABASE-RESTRICTED-CATALOG-V1
-- Purpose: Inspect database names visible through the restricted backend account directly.
-- Expected: The restricted account sees no D3d target databases.
-- Dialect: mysql

SHOW DATABASES LIKE 'sqlt_ddl_boundary_%';
