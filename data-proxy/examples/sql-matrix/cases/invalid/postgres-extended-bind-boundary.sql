-- case: SQLT-INVALID-015
-- Purpose: Verify PostgreSQL extended Bind rejects missing, extra, and invalid typed parameters.
-- Expected: Each failure reaches ReadyForQuery I and a valid Bind succeeds on the same connection.
-- Dialect: postgres

SELECT $1::INTEGER + 1 AS calculated_value;
