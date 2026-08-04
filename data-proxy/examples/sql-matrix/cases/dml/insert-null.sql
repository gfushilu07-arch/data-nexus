-- case: SQLT-DML-005
-- Purpose: Verify an explicit NULL in a nullable INSERT column.
-- Expected: The amount remains SQL NULL and the required status is stored.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3004, 'nullable amount', NULL, 'null-ok');
