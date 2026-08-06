-- oracle: SQLT-ORACLE-MYSQL-DDL-VIEWS-V1
-- Purpose: Produce stable MySQL object and projected-column metadata for the view under test.
-- Expected: Ordered VIEW rows include column name, type, and nullability.
-- Dialect: mysql

SELECT
    tables.table_type,
    columns.ordinal_position,
    columns.column_name,
    LOWER(columns.column_type),
    columns.is_nullable
FROM information_schema.tables AS tables
JOIN information_schema.columns AS columns
  ON columns.table_schema = tables.table_schema
 AND columns.table_name = tables.table_name
WHERE tables.table_schema = DATABASE()
  AND tables.table_name = 'sqlt_ddl_view'
ORDER BY columns.ordinal_position;
