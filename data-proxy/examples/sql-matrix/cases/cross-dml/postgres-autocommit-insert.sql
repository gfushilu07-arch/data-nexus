-- case: SQLT-XDML-001
-- Purpose: Verify a PostgreSQL simple INSERT is committed through a MySQL backend.
-- Expected: One row is affected and the inserted mutation is visible on the same connection.
-- Dialect: postgres

-- @step insert
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9301, 'cross insert', 10.50);
-- @step verify
SELECT mutation_id, description, amount, status
FROM sqlt_mutations WHERE mutation_id = 9301;
