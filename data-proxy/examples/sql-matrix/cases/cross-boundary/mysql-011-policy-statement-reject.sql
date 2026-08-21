-- case: SQLT-XBND-011
-- Purpose: Verify a statement outside the allowed translation subset is rejected cross-protocol.
-- Expected: The prepared CALL fails with a stable error; the canary row still returns.
-- Dialect: mysql

-- @step call
CALL sqlt_missing_procedure(1);
-- @step canary
SELECT 1 AS one;
