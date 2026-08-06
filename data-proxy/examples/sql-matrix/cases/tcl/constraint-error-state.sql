-- case: SQLT-TCL-006
-- Purpose: Observe dialect transaction state after a duplicate-key error without a savepoint recovery.
-- Expected: MySQL continues and commits; PostgreSQL aborts and rolls back at COMMIT.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9206, 'before constraint error', 20.06);
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9206, 'duplicate constraint error', 99.99);
UPDATE sqlt_mutations SET status = 'error-recovered' WHERE mutation_id = 9206;
COMMIT;
SELECT 'SQLT_TXN', 'constraint-state', COUNT(*),
       COALESCE(MAX(status), '<NONE>')
FROM sqlt_mutations WHERE mutation_id = 9206;
