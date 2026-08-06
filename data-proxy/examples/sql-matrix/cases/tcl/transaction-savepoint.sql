-- case: SQLT-TCL-001
-- Purpose: Verify transaction, savepoint, rollback-to-savepoint, and commit handling.
-- Expected: The first insert commits and the insert after the savepoint is rolled back.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9003, 'before savepoint', 30.00);
SAVEPOINT sqlt_checkpoint;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9004, 'after savepoint', 40.00);
ROLLBACK TO SAVEPOINT sqlt_checkpoint;
COMMIT;
SELECT 'SQLT_TXN', 'savepoint-rollback', mutation_id, status
FROM sqlt_mutations
WHERE mutation_id = 9003;
