-- case: SQLT-XDML-005
-- Purpose: Verify a PostgreSQL simple connection remains usable after a translated duplicate-key error.
-- Expected: The duplicate fails, SELECT 42 succeeds on the same connection, and only the seed remains.
-- Dialect: postgres

-- @step seed
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9305, 'constraint seed', 50.00);
-- @step duplicate
-- @expect error
INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9305, 'constraint duplicate', 51.00);
-- @step recover
SELECT 42 AS recovery_value;
-- @step verify
SELECT mutation_id, description, amount, status
FROM sqlt_mutations WHERE mutation_id = 9305;
