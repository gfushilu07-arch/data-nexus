-- oracle: SQLT-ORACLE-MYSQL-DDL-CONSTRAINTS-V1
-- Purpose: Produce stable MySQL constraint and key-column metadata for DDL probes.
-- Expected: One ordered TSV row per constraint column on sqlt_ddl_constraint.
-- Dialect: mysql

SELECT
    tc.constraint_name,
    tc.constraint_type,
    kcu.ordinal_position,
    kcu.column_name,
    COALESCE(kcu.referenced_table_name, '<NULL>'),
    COALESCE(kcu.referenced_column_name, '<NULL>')
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON kcu.constraint_schema = tc.constraint_schema
 AND kcu.table_name = tc.table_name
 AND kcu.constraint_name = tc.constraint_name
WHERE tc.constraint_schema = DATABASE()
  AND tc.table_name = 'sqlt_ddl_constraint'
ORDER BY tc.constraint_name, kcu.ordinal_position;
