-- case: SQLT-META-017
-- Purpose: Verify PostgreSQL constraint metadata for a fixture table.
-- Expected: Allow returns the primary key with stable ordering.
-- Dialect: postgres

SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'public'
  AND table_name = 'sqlt_customers'
ORDER BY constraint_name;
