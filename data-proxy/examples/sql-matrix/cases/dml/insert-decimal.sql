-- case: SQLT-DML-007
-- Purpose: Verify an exact DECIMAL or NUMERIC value at the fixture precision boundary.
-- Expected: The decimal value is stored as 1234567890.12 without floating-point rounding.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3006, 'exact decimal', 1234567890.12, 'precise');
