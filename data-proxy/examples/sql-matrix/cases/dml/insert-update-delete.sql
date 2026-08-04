-- case: SQLT-DML-001
-- Purpose: Verify portable INSERT, UPDATE, and DELETE statements in one transaction.
-- Expected: Allow commits all writes; deny or missing ticket prevents every write.
-- Dialect: mysql, postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9001, 'sqlt basic dml', 10.50);
UPDATE sqlt_mutations
SET amount = 11.75
WHERE mutation_id = 9001;
DELETE FROM sqlt_mutations
WHERE mutation_id = 9001;
COMMIT;
