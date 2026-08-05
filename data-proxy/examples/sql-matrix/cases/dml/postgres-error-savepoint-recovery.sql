-- case: SQLT-DML-043
-- Purpose: Verify PostgreSQL recovers an aborted transaction by rolling back to a savepoint.
-- Expected: The invalid update has no effect, a later update commits, and the marker query succeeds.
-- Dialect: postgres

BEGIN;
SAVEPOINT before_error;
UPDATE sqlt_dml_targets
SET customer_id = 999999
WHERE target_id = 4001;
ROLLBACK TO SAVEPOINT before_error;
UPDATE sqlt_dml_targets
SET status = 'error-recovered'
WHERE target_id = 4002;
SELECT 'SQLT_TXN', 'postgres-error-recovery', target_id, customer_id, status
FROM sqlt_dml_targets
WHERE target_id IN (4001, 4002)
ORDER BY target_id;
COMMIT;
