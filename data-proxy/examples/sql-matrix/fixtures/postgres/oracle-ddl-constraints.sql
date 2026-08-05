-- oracle: SQLT-ORACLE-POSTGRES-DDL-CONSTRAINTS-V1
-- Purpose: Produce stable PostgreSQL constraint and key-column metadata for DDL probes.
-- Expected: One ordered TSV row per constraint column on sqlt_ddl_constraint.
-- Dialect: postgres

SELECT
    tc.constraint_name,
    tc.constraint_type,
    kcu.ordinal_position,
    kcu.column_name,
    CASE WHEN tc.constraint_type = 'FOREIGN KEY' THEN ccu.table_name ELSE '<NULL>' END,
    CASE WHEN tc.constraint_type = 'FOREIGN KEY' THEN ccu.column_name ELSE '<NULL>' END
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON kcu.constraint_schema = tc.constraint_schema
 AND kcu.table_name = tc.table_name
 AND kcu.constraint_name = tc.constraint_name
LEFT JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_schema = tc.constraint_schema
 AND ccu.constraint_name = tc.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.table_name = 'sqlt_ddl_constraint'
ORDER BY tc.constraint_name, kcu.ordinal_position;
