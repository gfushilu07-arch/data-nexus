-- case: SQLT-DML-014
-- Purpose: Verify an INSERT whose status exceeds VARCHAR(32) is rejected by both backends.
-- Expected: The statement fails with the backend data-too-long identity and leaves the mutation table empty.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3014, 'too long status', 100.00, 'this status value is deliberately longer than thirty two');
