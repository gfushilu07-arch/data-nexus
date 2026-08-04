-- oracle: SQLT-ORACLE-POSTGRES-DML-TCL-V1
-- Purpose: Exercise PostgreSQL returned rows, savepoint rollback, update, and commit behavior.
-- Expected: Insert/update return one row; the rolled-back row is absent after commit.
-- Dialect: postgres

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9101, 'sqlt committed', 10.00)
RETURNING 'inserted', mutation_id;
SAVEPOINT sqlt_oracle_savepoint;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9102, 'sqlt rolled back', 20.00)
RETURNING 'inserted_after_savepoint', mutation_id;
ROLLBACK TO SAVEPOINT sqlt_oracle_savepoint;
UPDATE sqlt_mutations
SET amount = 11.25
WHERE mutation_id = 9101
RETURNING 'updated', mutation_id;
COMMIT;
