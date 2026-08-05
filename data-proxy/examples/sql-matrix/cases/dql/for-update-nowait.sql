-- case: SQLT-DQL-083
-- Purpose: Verify FOR UPDATE NOWAIT rejects an incompatible row lock without waiting.
-- Expected: A stable lock error is returned while held and the row succeeds after rollback.
-- Dialect: mysql, postgres

SELECT target_id
FROM sqlt_dml_targets
WHERE target_id = 4001
FOR UPDATE NOWAIT;
