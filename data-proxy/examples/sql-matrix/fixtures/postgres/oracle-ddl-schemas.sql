-- oracle: SQLT-ORACLE-POSTGRES-DDL-SCHEMAS-V1
-- Purpose: Produce stable namespace, owner, object, and column metadata for the test schema.
-- Expected: One schema row when empty or one ordered row per column of each contained object.
-- Dialect: postgres

SELECT
    namespaces.nspname,
    pg_get_userbyid(namespaces.nspowner),
    COALESCE(
        CASE objects.relkind
            WHEN 'r' THEN 'TABLE'
            WHEN 'p' THEN 'PARTITIONED TABLE'
            WHEN 'v' THEN 'VIEW'
            WHEN 'm' THEN 'MATERIALIZED VIEW'
            WHEN 'S' THEN 'SEQUENCE'
        END,
        '<NULL>'
    ),
    COALESCE(objects.relname, '<NULL>'),
    COALESCE(columns.attnum::text, '<NULL>'),
    COALESCE(columns.attname, '<NULL>'),
    COALESCE(format_type(columns.atttypid, columns.atttypmod), '<NULL>'),
    CASE
        WHEN columns.attnum IS NULL THEN '<NULL>'
        WHEN columns.attnotnull THEN 'NO'
        ELSE 'YES'
    END
FROM pg_namespace AS namespaces
LEFT JOIN pg_class AS objects
  ON objects.relnamespace = namespaces.oid
 AND objects.relkind IN ('r', 'p', 'v', 'm', 'S')
LEFT JOIN pg_attribute AS columns
  ON columns.attrelid = objects.oid
 AND columns.attnum > 0
 AND NOT columns.attisdropped
WHERE namespaces.nspname = 'sqlt_ddl_schema'
ORDER BY objects.relname, columns.attnum;
