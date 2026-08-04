-- case: SQLT-DML-013
-- Purpose: Verify an INSERT with a NULL required description fails without a partial write.
-- Expected: The statement fails with the backend NOT NULL identity and leaves the mutation table empty.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3013, NULL, 90.00, 'invalid-null');
