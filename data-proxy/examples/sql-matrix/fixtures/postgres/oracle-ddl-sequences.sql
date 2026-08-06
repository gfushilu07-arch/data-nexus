-- oracle: SQLT-ORACLE-POSTGRES-DDL-SEQUENCES-V1
-- Purpose: Produce stable PostgreSQL owner, parameter, and last-value metadata for the test sequence.
-- Expected: At most one row describes sqlt_ddl_sequence without advancing its runtime state.
-- Dialect: postgres

SELECT
    schemaname,
    sequencename,
    sequenceowner,
    data_type,
    start_value,
    min_value,
    max_value,
    increment_by,
    CASE WHEN cycle THEN 'YES' ELSE 'NO' END,
    cache_size,
    COALESCE(last_value::text, '<NULL>')
FROM pg_sequences
WHERE schemaname = 'public'
  AND sequencename = 'sqlt_ddl_sequence'
ORDER BY schemaname, sequencename;
