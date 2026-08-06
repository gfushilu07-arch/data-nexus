-- case: SQLT-INVALID-003
-- Purpose: Verify an incomplete SELECT is rejected at the grammar boundary.
-- Expected: The backend returns its stable syntax error and fixture state is unchanged.
-- Dialect: mysql, postgres

SELECT FROM;
