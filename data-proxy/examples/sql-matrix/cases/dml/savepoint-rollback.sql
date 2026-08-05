-- case: SQLT-DML-041
-- Purpose: Verify a successful DML change can be rolled back to a savepoint on the same connection.
-- Expected: Target 4001 remains unchanged, target 4002 records recovery, and the marker query succeeds.
-- Dialect: mysql, postgres

START TRANSACTION;
SAVEPOINT before_change;
UPDATE sqlt_dml_targets
SET description = 'must-rollback', status = 'must-rollback'
WHERE target_id = 4001;
ROLLBACK TO SAVEPOINT before_change;
UPDATE sqlt_dml_targets
SET status = 'savepoint-recovered'
WHERE target_id = 4002;
SELECT 'SQLT_TXN', 'savepoint-rollback', target_id, description, status
FROM sqlt_dml_targets
WHERE target_id IN (4001, 4002)
ORDER BY target_id;
COMMIT;
