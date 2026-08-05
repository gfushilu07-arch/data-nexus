-- case: SQLT-DQL-081
-- Purpose: Verify FOR UPDATE waits for an incompatible row lock to be released.
-- Expected: The selected row is returned only after the competing transaction rolls back.
-- Dialect: mysql, postgres

SELECT target_id
FROM sqlt_dml_targets
WHERE target_id = 4001
FOR UPDATE;
