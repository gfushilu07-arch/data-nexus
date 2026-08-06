-- case: SQLT-INVALID-004
-- Purpose: Verify a reference to a missing table has a stable error identity.
-- Expected: Name resolution fails and fixture state is unchanged.
-- Dialect: mysql, postgres

SELECT * FROM sqlt_missing_table;
