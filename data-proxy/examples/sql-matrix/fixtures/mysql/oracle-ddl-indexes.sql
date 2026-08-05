-- oracle: SQLT-ORACLE-MYSQL-DDL-INDEXES-V1
-- Purpose: Produce stable MySQL metadata for the named index under test.
-- Expected: Ordered index name, column ordinal, column name, and uniqueness rows.
-- Dialect: mysql

SELECT
    index_name,
    seq_in_index,
    column_name,
    CASE WHEN non_unique = 0 THEN 'YES' ELSE 'NO' END AS is_unique
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND table_name = 'sqlt_ddl_index'
  AND index_name = 'sqlt_idx_probe'
ORDER BY seq_in_index;
