-- case: SQLT-DML-004
-- Purpose: Verify a multi-row INSERT with explicit status values.
-- Expected: Both rows are committed and retain their exact decimal amounts and statuses.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES
    (3002, 'multi one', 20.00, 'queued'),
    (3003, 'multi two', 30.25, 'ready');
