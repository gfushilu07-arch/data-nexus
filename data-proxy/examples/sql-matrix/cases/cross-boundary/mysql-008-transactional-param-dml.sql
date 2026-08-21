-- case: SQLT-XBND-008
-- Purpose: Verify parameterized DML commits and rolls back inside cross-protocol transactions.
-- Expected: The committed insert persists; the rolled-back update leaves the amount unchanged.
-- Dialect: mysql

-- @step begin
BEGIN;
-- @step insert
INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (?, ?, ?, ?);
-- @step commit
COMMIT;
-- @step verify
SELECT mutation_id, description, amount, status FROM sqlt_mutations WHERE mutation_id = ?;
-- @step begin_rollback
BEGIN;
-- @step update
UPDATE sqlt_mutations SET amount = ? WHERE mutation_id = ?;
-- @step rollback
ROLLBACK;
-- @step verify_rollback
SELECT amount FROM sqlt_mutations WHERE mutation_id = ?;
