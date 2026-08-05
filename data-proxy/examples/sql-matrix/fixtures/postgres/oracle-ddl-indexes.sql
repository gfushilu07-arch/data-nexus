-- oracle: SQLT-ORACLE-POSTGRES-DDL-INDEXES-V1
-- Purpose: Produce stable PostgreSQL metadata for the named index under test.
-- Expected: Ordered index name, column ordinal, column name, and uniqueness rows.
-- Dialect: postgres

SELECT
    index_class.relname,
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
  AND table_class.relname = 'sqlt_ddl_index'
  AND index_class.relname = 'sqlt_idx_probe'
ORDER BY key_column.ordinality;
