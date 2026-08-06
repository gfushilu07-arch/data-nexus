-- oracle: SQLT-ORACLE-POSTGRES-DDL-VIEWS-V1
-- Purpose: Produce stable PostgreSQL object and projected-column metadata for the view under test.
-- Expected: Ordered VIEW rows include column name, type, and nullability.
-- Dialect: postgres

SELECT
    tables.table_type,
    columns.ordinal_position,
    columns.column_name,
    CASE
        WHEN columns.data_type = 'character varying'
             AND columns.character_maximum_length IS NOT NULL
            THEN columns.data_type || '(' || columns.character_maximum_length || ')'
        ELSE columns.data_type
    END,
    columns.is_nullable
FROM information_schema.tables AS tables
JOIN information_schema.columns AS columns
  ON columns.table_schema = tables.table_schema
 AND columns.table_name = tables.table_name
WHERE tables.table_schema = 'public'
  AND tables.table_name = 'sqlt_ddl_view'
ORDER BY columns.ordinal_position;
