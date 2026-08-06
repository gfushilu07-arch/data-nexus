-- case: SQLT-INVALID-016
-- Purpose: Verify a failing multi-statement simple Query cannot leave a partial mutation.
-- Expected: The missing-table error rolls back the preceding insert and the connection recovers.
-- Dialect: postgres

INSERT INTO sqlt_mutations (mutation_id, description)
VALUES (9916, 'must-roll-back');
SELECT * FROM sqlt_missing_table;
