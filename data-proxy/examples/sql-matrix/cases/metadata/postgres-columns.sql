-- case: SQLT-META-015
-- Purpose: Verify PostgreSQL information_schema column metadata for a fixture table.
-- Expected: Allow returns ordered column names, types, and nullability.
-- Dialect: postgres

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'sqlt_customers'
ORDER BY ordinal_position;
