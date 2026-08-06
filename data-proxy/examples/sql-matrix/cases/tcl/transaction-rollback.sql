-- case: SQLT-TCL-003
-- Purpose: Roll back one mutation in an explicit transaction.
-- Expected: The mutation is absent after ROLLBACK and the connection remains usable.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9203, 'transaction rollback', 20.03);
ROLLBACK;
SELECT 'SQLT_TXN', 'rollback', COUNT(*)
FROM sqlt_mutations WHERE mutation_id = 9203;
