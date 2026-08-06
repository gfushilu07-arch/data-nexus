-- case: SQLT-TCL-011
-- Purpose: Recover a duplicate-key error by rolling back to and releasing a savepoint.
-- Expected: The invalid insert is discarded, a later update commits, and the transaction remains usable.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9210, 'savepoint recovery', 21.10);
SAVEPOINT before_tcl_error;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9210, 'duplicate savepoint error', 99.99);
ROLLBACK TO SAVEPOINT before_tcl_error;
RELEASE SAVEPOINT before_tcl_error;
UPDATE sqlt_mutations SET status = 'error-recovered' WHERE mutation_id = 9210;
COMMIT;
SELECT 'SQLT_TXN', 'savepoint-error-recovery', mutation_id, status
FROM sqlt_mutations WHERE mutation_id = 9210;
