-- oracle: SQLT-ORACLE-MYSQL-DDL-CHECK-V1
-- Purpose: Produce stable MySQL check metadata and protected-table row count.
-- Expected: The named check is present and the violating probe leaves zero rows.
-- Dialect: mysql

SELECT
    '<ROW_COUNT>' AS constraint_name,
    'DATA ROWS' AS constraint_type,
    COUNT(*) AS ordinal_or_count,
    '<NULL>' AS column_name,
    '<NULL>' AS referenced_table_name,
    '<NULL>' AS referenced_column_name
FROM sqlt_ddl_constraint
UNION ALL
SELECT
    tc.constraint_name,
    tc.constraint_type,
    0,
    '<NULL>',
    '<NULL>',
    '<NULL>'
FROM information_schema.table_constraints AS tc
WHERE tc.constraint_schema = DATABASE()
  AND tc.table_name = 'sqlt_ddl_constraint'
  AND tc.constraint_name = 'sqlt_ck_probe'
ORDER BY constraint_name;
