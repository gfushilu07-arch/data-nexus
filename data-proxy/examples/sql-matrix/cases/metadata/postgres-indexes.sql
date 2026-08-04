-- case: SQLT-META-016
-- Purpose: Verify PostgreSQL index catalog metadata for a fixture table.
-- Expected: Allow returns the primary-key index; deny returns no catalog data.
-- Dialect: postgres

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'sqlt_customers'
ORDER BY indexname;
