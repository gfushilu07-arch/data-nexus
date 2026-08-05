-- oracle: SQLT-ORACLE-POSTGRES-DDL-TRUNCATE-DATA-V1
-- Purpose: Count PostgreSQL rows before and after the canonical TRUNCATE case.
-- Expected: The deterministic count changes from three to zero.
-- Dialect: postgres

SELECT COUNT(*) FROM sqlt_ddl_truncate;
