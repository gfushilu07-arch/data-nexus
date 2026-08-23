-- case: SQLT-GOV-005
-- Purpose: Verify a five-row ordered read under obligation policies.
-- Expected: Baseline returns all five targets; obligations cap, mask, or tag the result set.
-- Dialect: postgres

-- @step select
SELECT target_id, description, amount, status FROM sqlt_dml_targets ORDER BY target_id;
