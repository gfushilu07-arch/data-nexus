-- oracle: SQLT-ORACLE-MYSQL-DML-TCL-STATE-V1
-- Purpose: Inspect committed MySQL mutation state independently of the execution path.
-- Expected: Only mutation 9101 exists with amount 11.25 and mutation 9102 is absent.
-- Dialect: mysql

SELECT mutation_id, description, amount
FROM sqlt_mutations
ORDER BY mutation_id;
