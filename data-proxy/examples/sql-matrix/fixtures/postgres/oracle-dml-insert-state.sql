-- oracle: SQLT-ORACLE-POSTGRES-DML-INSERT-STATE-V1
-- Purpose: Inspect every PostgreSQL row that a SQLT-3C1 INSERT case may create.
-- Expected: Mutation and test-order rows are returned in stable entity and ID order.
-- Dialect: postgres

SELECT entity, entity_id, description, amount, status
FROM (
    SELECT
        'mutation'::text AS entity,
        mutation_id AS entity_id,
        description,
        COALESCE(amount::text, 'NULL') AS amount,
        status
    FROM sqlt_mutations
    UNION ALL
    SELECT
        'order'::text AS entity,
        order_id AS entity_id,
        customer_id::text AS description,
        total_amount::text AS amount,
        status
    FROM sqlt_orders
    WHERE order_id >= 3000
) AS insert_state
ORDER BY entity, entity_id;
