-- case: SQLT-DML-003
-- Purpose: Verify a single INSERT with an explicit column list and non-table column order.
-- Expected: One mutation is inserted with the omitted status column set to its default.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (description, mutation_id, amount)
VALUES ('single insert', 3001, 10.50);
