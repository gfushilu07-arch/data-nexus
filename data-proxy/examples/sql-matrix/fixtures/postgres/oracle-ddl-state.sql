-- oracle: SQLT-ORACLE-POSTGRES-DDL-STATE-V1
-- Purpose: Inspect PostgreSQL schema state independently after the DDL lifecycle.
-- Expected: No sqlt_ddl_oracle table remains in the public schema.
-- Dialect: postgres

SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'sqlt_ddl_oracle';
