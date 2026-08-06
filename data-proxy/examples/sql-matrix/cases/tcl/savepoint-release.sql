-- case: SQLT-TCL-004
-- Purpose: Release a savepoint and prove it can no longer be targeted.
-- Expected: ROLLBACK TO the released savepoint fails, full ROLLBACK recovers, and no row remains.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9204, 'released savepoint', 20.04);
SAVEPOINT sqlt_released;
RELEASE SAVEPOINT sqlt_released;
ROLLBACK TO SAVEPOINT sqlt_released;
ROLLBACK;
SELECT 'SQLT_TXN', 'released', COUNT(*)
FROM sqlt_mutations WHERE mutation_id = 9204;
