-- case: SQLT-XDML-007
-- Purpose: Verify an explicit MySQL text transaction rolls back through a PostgreSQL backend.
-- Expected: The inserted mutation is absent after ROLLBACK and the same connection remains usable.
-- Dialect: mysql

-- @step begin
BEGIN;
-- @step insert
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9307, 'rolled back mutation', 70.00);
-- @step rollback
ROLLBACK;
-- @step verify
SELECT COUNT(*) AS remaining FROM sqlt_mutations WHERE mutation_id = 9307;
