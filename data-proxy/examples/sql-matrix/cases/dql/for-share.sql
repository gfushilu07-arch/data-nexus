-- case: SQLT-DQL-082
-- Purpose: Verify FOR SHARE permits a concurrent shared lock while excluding an update lock.
-- Expected: A second shared read succeeds immediately and an update NOWAIT probe is rejected.
-- Dialect: mysql, postgres

SELECT target_id
FROM sqlt_dml_targets
WHERE target_id = 4001
FOR SHARE;
