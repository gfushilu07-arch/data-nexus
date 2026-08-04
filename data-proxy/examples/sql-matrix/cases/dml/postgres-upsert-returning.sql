-- case: SQLT-DML-002
-- Purpose: Verify PostgreSQL ON CONFLICT update and RETURNING result metadata.
-- Expected: Allow returns the upserted row; deny or missing ticket leaves data unchanged.
-- Dialect: postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9002, 'sqlt upsert', 20.00)
ON CONFLICT (mutation_id) DO UPDATE
SET description = EXCLUDED.description,
    amount = EXCLUDED.amount
RETURNING mutation_id, description, amount;
