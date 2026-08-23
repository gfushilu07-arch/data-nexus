-- oracle: SQLT-ORACLE-POSTGRES-GOVERNANCE-STATE-V1
-- Purpose: Inspect fixture liveness and SQLT-5A governance mutation rows on a PostgreSQL backend.
-- Expected: Four customers survive policy rejects; mutation rows 9500-9599 are counted in ID order.
-- Dialect: postgres

SELECT 'customers' AS entity, COUNT(*) AS cnt FROM sqlt_customers
UNION ALL
SELECT 'mutations' AS entity, COUNT(*) AS cnt
FROM sqlt_mutations WHERE mutation_id BETWEEN 9500 AND 9599;
