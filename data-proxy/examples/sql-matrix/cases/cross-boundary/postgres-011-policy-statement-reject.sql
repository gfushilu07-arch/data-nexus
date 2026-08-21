-- case: SQLT-XBND-011
-- Purpose: Verify a statement outside the allowed translation subset is rejected cross-protocol.
-- Expected: The extended CALL execute fails with a stable error; Sync returns idle and the canary row returns.
-- Dialect: postgres

-- @step call
CALL sqlt_missing_procedure(1);
-- @step canary
SELECT 1 AS one;
