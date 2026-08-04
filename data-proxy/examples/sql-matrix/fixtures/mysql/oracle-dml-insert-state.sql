-- oracle: SQLT-ORACLE-MYSQL-DML-INSERT-STATE-V1
-- Purpose: Inspect every MySQL row that a SQLT-3C1 INSERT case may create.
-- Expected: Mutation and test-order rows are returned in stable entity and ID order.
-- Dialect: mysql

SELECT entity, entity_id, description, amount, status
FROM (
    SELECT
        'mutation' AS entity,
        mutation_id AS entity_id,
        description,
        COALESCE(CAST(amount AS CHAR), 'NULL') AS amount,
        status
    FROM sqlt_mutations
    UNION ALL
    SELECT
        'order' AS entity,
        order_id AS entity_id,
        CAST(customer_id AS CHAR) AS description,
        CAST(total_amount AS CHAR) AS amount,
        status
    FROM sqlt_orders
    WHERE order_id >= 3000
) AS insert_state
ORDER BY entity, entity_id;
