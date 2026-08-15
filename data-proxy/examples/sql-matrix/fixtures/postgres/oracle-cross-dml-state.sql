-- oracle: SQLT-ORACLE-POSTGRES-CROSS-DML-STATE-V1
-- Purpose: Inspect every row touched by SQLT-4B2 on a PostgreSQL backend.
-- Expected: Target and cross-DML mutation rows are returned in stable entity and ID order.
-- Dialect: postgres

SELECT entity, entity_id, description, amount, status
FROM (
    SELECT 'target'::text AS entity, target_id AS entity_id, description,
           COALESCE(amount::text, 'NULL') AS amount, status
    FROM sqlt_dml_targets
    UNION ALL
    SELECT 'mutation'::text AS entity, mutation_id AS entity_id, description,
           COALESCE(amount::text, 'NULL') AS amount, status
    FROM sqlt_mutations
    WHERE mutation_id BETWEEN 9300 AND 9399
) AS cross_dml_state
ORDER BY entity, entity_id;
