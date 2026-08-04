-- oracle: SQLT-ORACLE-POSTGRES-ERROR-V1
-- Purpose: Produce a stable PostgreSQL undefined-column error without backend side effects.
-- Expected: Direct and gateway paths fail with SQLSTATE 42703.
-- Dialect: postgres

SELECT missing_sqlt_column
FROM sqlt_customers;
