-- oracle: SQLT-ORACLE-POSTGRES-CROSS-BOUNDARY-STATE-V1
-- Purpose: Inspect fixture liveness and SQLT-4B3 mutation rows on a PostgreSQL backend.
-- Expected: Four customers survive DDL rejects; mutation rows 9400-9499 are listed in ID order.
-- Dialect: postgres

SELECT 'customers' AS entity, COUNT(*) AS cnt FROM sqlt_customers
UNION ALL
SELECT 'mutations' AS entity, COUNT(*) AS cnt
FROM sqlt_mutations WHERE mutation_id BETWEEN 9400 AND 9499;
