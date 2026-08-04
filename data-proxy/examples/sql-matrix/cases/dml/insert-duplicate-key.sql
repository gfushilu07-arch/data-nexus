-- case: SQLT-DML-011
-- Purpose: Verify a duplicate primary key INSERT fails atomically.
-- Expected: The statement fails with the backend duplicate-key identity and leaves the mutation table empty.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES
    (3011, 'first row', 70.00, 'first'),
    (3011, 'duplicate row', 71.00, 'duplicate');
