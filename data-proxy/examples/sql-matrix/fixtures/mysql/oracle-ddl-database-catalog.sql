-- oracle: SQLT-ORACLE-MYSQL-DDL-DATABASE-CATALOG-V1
-- Purpose: Inspect database charset and collation for the D3d target.
-- Expected: One stable row when root prepared the target, otherwise no rows.
-- Dialect: mysql

SELECT schema_name, default_character_set_name, default_collation_name
FROM information_schema.schemata
WHERE schema_name LIKE 'sqlt_ddl_boundary_%'
ORDER BY schema_name;
