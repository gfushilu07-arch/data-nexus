-- case: SQLT-TCL-005
-- Purpose: Roll back nested and outer savepoints in order.
-- Expected: Only the row written before the outer savepoint commits.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9205, 'before outer savepoint', 20.05);
SAVEPOINT sqlt_outer;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9255, 'inside outer savepoint', 25.55);
SAVEPOINT sqlt_inner;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9256, 'inside inner savepoint', 25.56);
ROLLBACK TO SAVEPOINT sqlt_inner;
ROLLBACK TO SAVEPOINT sqlt_outer;
COMMIT;
SELECT 'SQLT_TXN', 'nested', mutation_id, status
FROM sqlt_mutations WHERE mutation_id BETWEEN 9205 AND 9256 ORDER BY mutation_id;
