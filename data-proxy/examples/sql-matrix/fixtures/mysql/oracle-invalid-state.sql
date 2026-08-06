-- fixture: SQLT-FIXTURE-MYSQL-INVALID-STATE-V1
-- Purpose: Capture deterministic row state before and after an invalid statement.
-- Expected: Counts and the protected target row remain identical.
-- Dialect: mysql

SELECT
    (SELECT COUNT(*) FROM sqlt_customers),
    (SELECT COUNT(*) FROM sqlt_orders),
    (SELECT COUNT(*) FROM sqlt_mutations),
    (SELECT COUNT(*) FROM sqlt_dml_targets),
    (SELECT description FROM sqlt_dml_targets WHERE target_id = 4001),
    (SELECT amount FROM sqlt_dml_targets WHERE target_id = 4001);
