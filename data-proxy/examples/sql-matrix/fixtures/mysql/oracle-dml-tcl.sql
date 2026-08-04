-- oracle: SQLT-ORACLE-MYSQL-DML-TCL-V1
-- Purpose: Exercise MySQL affected rows, savepoint rollback, update, and commit behavior.
-- Expected: Insert/update affect one row; the rolled-back row is absent after commit.
-- Dialect: mysql

BEGIN;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9101, 'sqlt committed', 10.00);
SELECT 'inserted', ROW_COUNT();
SAVEPOINT sqlt_oracle_savepoint;
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9102, 'sqlt rolled back', 20.00);
SELECT 'inserted_after_savepoint', ROW_COUNT();
ROLLBACK TO SAVEPOINT sqlt_oracle_savepoint;
UPDATE sqlt_mutations
SET amount = 11.25
WHERE mutation_id = 9101;
SELECT 'updated', ROW_COUNT();
COMMIT;
