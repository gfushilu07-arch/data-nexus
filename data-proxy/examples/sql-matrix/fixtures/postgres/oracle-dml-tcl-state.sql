-- oracle: SQLT-ORACLE-POSTGRES-DML-TCL-STATE-V1
-- Purpose: Inspect committed PostgreSQL mutation state independently of the execution path.
-- Expected: Only mutation 9101 exists with amount 11.25 and mutation 9102 is absent.
-- Dialect: postgres

SELECT mutation_id, description, amount
FROM sqlt_mutations
ORDER BY mutation_id;
