-- case: SQLT-INVALID-007
-- Purpose: Verify invalid text cannot be assigned to an integer key.
-- Expected: The write fails with a stable type error and inserts no mutation row.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description)
VALUES ('not-an-integer', 'must-not-write');
