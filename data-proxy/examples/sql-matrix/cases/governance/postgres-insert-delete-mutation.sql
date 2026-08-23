-- case: SQLT-GOV-004
-- Purpose: Verify an insert/delete script under DML denial.
-- Expected: Baseline inserts then deletes 9502 leaving no row; both steps fail closed under the deny policy.
-- Dialect: postgres

-- @step insert
INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (9502, 'governance cycle', 12.75, 'new');
-- @step delete
DELETE FROM sqlt_mutations WHERE mutation_id = 9502;
-- @step verify_count
SELECT COUNT(*) AS remaining FROM sqlt_mutations WHERE mutation_id = 9502;
