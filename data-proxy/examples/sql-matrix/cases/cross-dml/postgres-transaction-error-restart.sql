-- case: SQLT-XDML-008
-- Purpose: Verify a failed PostgreSQL simple transaction can roll back and start a clean translated transaction.
-- Expected: The failed transaction leaves no row and the restarted transaction commits exactly one row.
-- Dialect: postgres

-- @step begin_failed
BEGIN;
-- @step seed_failed
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9308, 'failed transaction seed', 80.00);
-- @step duplicate
-- @expect error
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9308, 'failed transaction duplicate', 81.00);
-- @step rollback_failed
ROLLBACK;
-- @step begin_restart
BEGIN;
-- @step insert_restart
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9309, 'restarted transaction', 90.00);
-- @step commit_restart
COMMIT;
-- @step verify
SELECT mutation_id, description, amount, status
FROM sqlt_mutations WHERE mutation_id IN (9308, 9309)
ORDER BY mutation_id;
