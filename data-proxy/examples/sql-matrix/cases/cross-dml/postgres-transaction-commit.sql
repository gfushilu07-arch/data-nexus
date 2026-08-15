-- case: SQLT-XDML-006
-- Purpose: Verify an explicit PostgreSQL simple transaction commits through a MySQL backend.
-- Expected: BEGIN, INSERT, and COMMIT share one backend connection and persist the mutation.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step insert
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9306, 'committed mutation', 60.00);
-- @step commit
COMMIT;
-- @step verify
SELECT mutation_id, description, amount, status
FROM sqlt_mutations WHERE mutation_id = 9306;
