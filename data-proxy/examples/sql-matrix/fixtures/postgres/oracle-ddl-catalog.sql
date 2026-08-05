-- oracle: SQLT-ORACLE-POSTGRES-DDL-CATALOG-V1
-- Purpose: Produce stable PostgreSQL column metadata for canonical DDL test objects.
-- Expected: One ordered TSV row per column under the sqlt_ddl_ table prefix.
-- Dialect: postgres

SELECT
    table_name,
    ordinal_position,
    column_name,
    CASE
        WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL
            THEN data_type || '(' || character_maximum_length || ')'
        ELSE data_type
    END,
    is_nullable,
    COALESCE(column_default, '<NULL>')
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE 'sqlt\_ddl\_%' ESCAPE '\'
ORDER BY table_name, ordinal_position;
