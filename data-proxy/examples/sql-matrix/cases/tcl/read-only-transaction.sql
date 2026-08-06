-- case: SQLT-TCL-007
-- Purpose: Reject a write in a read-only transaction and recover with ROLLBACK.
-- Expected: The write fails with the dialect error identity and no mutation remains.
-- Dialect: mysql, postgres

START TRANSACTION READ ONLY;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9207, 'read only rejected', 20.07);
ROLLBACK;
SELECT 'SQLT_TXN', 'read-only', COUNT(*)
FROM sqlt_mutations WHERE mutation_id = 9207;
