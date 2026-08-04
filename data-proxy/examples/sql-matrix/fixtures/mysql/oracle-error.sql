-- oracle: SQLT-ORACLE-MYSQL-ERROR-V1
-- Purpose: Produce a stable MySQL unknown-column error without backend side effects.
-- Expected: Direct and gateway paths fail with error 1054 and SQLSTATE 42S22.
-- Dialect: mysql

SELECT missing_sqlt_column
FROM sqlt_customers;
