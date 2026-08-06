-- case: SQLT-INVALID-009
-- Purpose: Verify an out-of-range decimal cannot be inserted into NUMERIC(12,2).
-- Expected: The write fails with a stable range error and inserts no mutation row.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount)
VALUES (9909, 'must-not-write', 10000000000.00);
