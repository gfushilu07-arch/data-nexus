-- case: SQLT-INVALID-012
-- Purpose: Verify PostgreSQL rejects a function call with no matching signature.
-- Expected: Function resolution fails with SQLSTATE 42883 and fixture state is unchanged.
-- Dialect: postgres

SELECT lower(42);
