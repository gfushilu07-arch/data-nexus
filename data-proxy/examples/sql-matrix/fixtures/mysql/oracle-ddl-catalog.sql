-- oracle: SQLT-ORACLE-MYSQL-DDL-CATALOG-V1
-- Purpose: Produce stable MySQL column metadata for canonical DDL test objects.
-- Expected: One ordered TSV row per column under the sqlt_ddl_ table prefix.
-- Dialect: mysql

SELECT
    table_name,
    ordinal_position,
    column_name,
    LOWER(column_type),
    is_nullable,
    COALESCE(column_default, '<NULL>')
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name LIKE 'sqlt\_ddl\_%'
ORDER BY table_name, ordinal_position;
