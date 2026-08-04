-- case: SQLT-DML-006
-- Purpose: Verify the DEFAULT keyword and a column default during INSERT.
-- Expected: The status column contains the schema default value new.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3005, 'default status', 40.00, DEFAULT);
