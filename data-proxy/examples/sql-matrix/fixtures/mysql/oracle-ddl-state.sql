-- oracle: SQLT-ORACLE-MYSQL-DDL-STATE-V1
-- Purpose: Inspect MySQL schema state independently after the DDL lifecycle.
-- Expected: No sqlt_ddl_oracle table remains in the sqlt database.
-- Dialect: mysql

SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'sqlt'
  AND table_name = 'sqlt_ddl_oracle';
