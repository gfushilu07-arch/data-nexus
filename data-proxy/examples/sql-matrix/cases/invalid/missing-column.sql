-- case: SQLT-INVALID-005
-- Purpose: Verify a reference to a missing column has a stable error identity.
-- Expected: Column resolution fails and fixture state is unchanged.
-- Dialect: mysql, postgres

SELECT missing_column FROM sqlt_customers;
