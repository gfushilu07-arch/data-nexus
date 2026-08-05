-- oracle: SQLT-ORACLE-MYSQL-DDL-UNIQUE-V1
-- Purpose: Produce stable MySQL unique-constraint and implicit-index metadata.
-- Expected: Ordered constraint and unique-index rows for sqlt_uq_probe.
-- Dialect: mysql

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
WHERE tc.constraint_schema = DATABASE()
  AND tc.table_name = 'sqlt_ddl_constraint'
  AND tc.constraint_name = 'sqlt_uq_probe'
UNION ALL
SELECT
    'INDEX',
    s.index_name,
    'UNIQUE INDEX',
    s.seq_in_index,
    s.column_name,
    CASE WHEN s.non_unique = 0 THEN 'YES' ELSE 'NO' END
FROM information_schema.statistics AS s
WHERE s.table_schema = DATABASE()
  AND s.table_name = 'sqlt_ddl_constraint'
  AND s.index_name = 'sqlt_uq_probe'
ORDER BY object_kind, ordinal_position;
