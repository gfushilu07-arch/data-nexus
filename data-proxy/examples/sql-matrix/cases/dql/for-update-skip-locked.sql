-- case: SQLT-DQL-084
-- Purpose: Verify FOR UPDATE SKIP LOCKED omits locked rows from a deterministic range.
-- Expected: Only row 4002 is returned while 4001 is locked; both return after rollback.
-- Dialect: mysql, postgres

SELECT target_id
FROM sqlt_dml_targets
WHERE target_id IN (4001, 4002)
ORDER BY target_id
FOR UPDATE SKIP LOCKED;
