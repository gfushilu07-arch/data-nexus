-- oracle: SQLT-ORACLE-POSTGRES-DDL-UNIQUE-V1
-- Purpose: Produce stable PostgreSQL unique-constraint and implicit-index metadata.
-- Expected: Ordered constraint and unique-index rows for sqlt_uq_probe.
-- Dialect: postgres

SELECT
    'CONSTRAINT' AS object_kind,
    tc.constraint_name AS object_name,
    tc.constraint_type AS object_type,
    kcu.ordinal_position,
    kcu.column_name,
    'YES' AS is_unique
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON kcu.constraint_schema = tc.constraint_schema
 AND kcu.table_name = tc.table_name
 AND kcu.constraint_name = tc.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.table_name = 'sqlt_ddl_constraint'
  AND tc.constraint_name = 'sqlt_uq_probe'
UNION ALL
SELECT
    'INDEX',
    index_class.relname,
    'UNIQUE INDEX',
    key_column.ordinality::bigint,
    attribute.attname,
    CASE WHEN index_data.indisunique THEN 'YES' ELSE 'NO' END
FROM pg_catalog.pg_class AS table_class
JOIN pg_catalog.pg_namespace AS namespace
  ON namespace.oid = table_class.relnamespace
JOIN pg_catalog.pg_index AS index_data
  ON index_data.indrelid = table_class.oid
JOIN pg_catalog.pg_class AS index_class
  ON index_class.oid = index_data.indexrelid
CROSS JOIN LATERAL unnest(index_data.indkey)
  WITH ORDINALITY AS key_column(attribute_number, ordinality)
JOIN pg_catalog.pg_attribute AS attribute
  ON attribute.attrelid = table_class.oid
 AND attribute.attnum = key_column.attribute_number
WHERE namespace.nspname = 'public'
  AND table_class.relname = 'sqlt_ddl_constraint'
  AND index_class.relname = 'sqlt_uq_probe'
ORDER BY object_kind, ordinal_position;
