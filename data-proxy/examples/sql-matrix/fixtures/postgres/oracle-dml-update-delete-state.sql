-- oracle: SQLT-ORACLE-POSTGRES-DML-UPDATE-DELETE-STATE-V1
-- Purpose: Inspect every PostgreSQL row targeted by SQLT-3C2 UPDATE and DELETE cases.
-- Expected: All remaining DML target rows are returned in stable target ID order.
-- Dialect: postgres

SELECT target_id, customer_id, tenant_id, description,
       COALESCE(amount::text, 'NULL') AS amount, status
FROM sqlt_dml_targets
ORDER BY target_id;
