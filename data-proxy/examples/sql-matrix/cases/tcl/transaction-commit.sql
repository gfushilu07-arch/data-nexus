-- case: SQLT-TCL-002
-- Purpose: Commit one mutation in an explicit transaction.
-- Expected: The mutation remains visible after COMMIT and the connection can query it.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9202, 'transaction commit', 20.02);
COMMIT;
SELECT 'SQLT_TXN', 'commit', mutation_id, status
FROM sqlt_mutations WHERE mutation_id = 9202;
