-- oracle: SQLT-ORACLE-MYSQL-DML-UPDATE-DELETE-STATE-V1
-- Purpose: Inspect every MySQL row targeted by SQLT-3C2 UPDATE and DELETE cases.
-- Expected: All remaining DML target rows are returned in stable target ID order.
-- Dialect: mysql

SELECT target_id, customer_id, tenant_id, description,
       COALESCE(CAST(amount AS CHAR), 'NULL') AS amount, status
FROM sqlt_dml_targets
ORDER BY target_id;
