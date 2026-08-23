-- case: SQLT-GOV-002
-- Purpose: Verify a single dml_targets read under table-level SELECT denial.
-- Expected: Baseline returns the 4001 row; the deny policy rejects with security_deny and no leak.
-- Dialect: postgres

-- @step select
SELECT target_id, description, amount, status FROM sqlt_dml_targets WHERE target_id = 4001;
