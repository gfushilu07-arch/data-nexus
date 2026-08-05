-- case: SQLT-DQL-073
-- Purpose: Verify PostgreSQL array construction and one-based indexing preserve integer values.
-- Expected: Selected customer and tenant IDs are recovered from fixed array positions.
-- Dialect: postgres

SELECT customer_id,
       (ARRAY[customer_id, tenant_id::BIGINT])[1],
       (ARRAY[customer_id, tenant_id::BIGINT])[2]
FROM sqlt_customers
WHERE customer_id IN (101, 201)
ORDER BY customer_id;
