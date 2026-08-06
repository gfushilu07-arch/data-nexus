-- case: SQLT-INVALID-002
-- Purpose: Verify an unterminated string literal is rejected without executing a statement.
-- Expected: The backend returns its stable syntax error and fixture state is unchanged.
-- Dialect: mysql, postgres

SELECT 'unterminated;
