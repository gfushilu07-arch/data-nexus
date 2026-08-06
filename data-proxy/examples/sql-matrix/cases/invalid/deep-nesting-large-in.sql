-- case: SQLT-INVALID-020
-- Purpose: Verify fixed deep nesting and a large IN list remain bounded and deterministic.
-- Expected: The generated expression completes or fails predictably and the connection remains reusable.
-- Dialect: mysql, postgres

-- @generate nesting=64 in_items=2048
SELECT 1 AS generated_boundary;
