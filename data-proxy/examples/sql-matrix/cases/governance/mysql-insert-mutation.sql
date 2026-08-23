-- case: SQLT-GOV-003
-- Purpose: Verify a single mutation write under DML denial.
-- Expected: Baseline persists 9501; the deny policy rejects before any backend write and state stays empty.
-- Dialect: mysql

-- @step insert
INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (9501, 'governance insert', 55.25, 'new');
