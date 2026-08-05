-- oracle: SQLT-ORACLE-POSTGRES-DDL-CHECK-V1
-- Purpose: Produce stable PostgreSQL check metadata and protected-table row count.
-- Expected: The named check is present and the violating probe leaves zero rows.
-- Dialect: postgres

SELECT
    '<ROW_COUNT>'::text AS constraint_name,
    'DATA ROWS'::text AS constraint_type,
    COUNT(*)::bigint AS ordinal_or_count,
    '<NULL>'::text AS column_name,
    '<NULL>'::text AS referenced_table_name,
    '<NULL>'::text AS referenced_column_name
FROM sqlt_ddl_constraint
UNION ALL
SELECT
    tc.constraint_name,
    tc.constraint_type,
    0::bigint,
    '<NULL>',
    '<NULL>',
    '<NULL>'
FROM information_schema.table_constraints AS tc
WHERE tc.table_schema = 'public'
  AND tc.table_name = 'sqlt_ddl_constraint'
  AND tc.constraint_name = 'sqlt_ck_probe'
ORDER BY constraint_name;
