-- oracle: SQLT-ORACLE-MYSQL-CROSS-DML-STATE-V1
-- Purpose: Inspect every row touched by SQLT-4B2 on a MySQL backend.
-- Expected: Target and cross-DML mutation rows are returned in stable entity and ID order.
-- Dialect: mysql

SELECT entity, entity_id, description, amount, status
FROM (
    SELECT 'target' AS entity, target_id AS entity_id, description,
           COALESCE(CAST(amount AS CHAR), 'NULL') AS amount, status
    FROM sqlt_dml_targets
    UNION ALL
    SELECT 'mutation' AS entity, mutation_id AS entity_id, description,
           COALESCE(CAST(amount AS CHAR), 'NULL') AS amount, status
    FROM sqlt_mutations
    WHERE mutation_id BETWEEN 9300 AND 9399
) AS cross_dml_state
ORDER BY entity, entity_id;
