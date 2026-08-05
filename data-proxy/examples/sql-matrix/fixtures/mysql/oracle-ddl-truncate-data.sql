-- oracle: SQLT-ORACLE-MYSQL-DDL-TRUNCATE-DATA-V1
-- Purpose: Count MySQL rows before and after the canonical TRUNCATE case.
-- Expected: The deterministic count changes from three to zero.
-- Dialect: mysql

SELECT COUNT(*) FROM sqlt_ddl_truncate;
