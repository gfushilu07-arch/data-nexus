-- case: SQLT-DQL-053
-- Purpose: Verify MOD and POWER arithmetic functions over bounded integer IDs.
-- Expected: Every order returns its ID modulo ten and the square of its tenant ID.
-- Dialect: mysql, postgres

SELECT order_id,
       MOD(order_id, 10) AS id_remainder,
       POWER(tenant_id, 2) AS tenant_square
FROM sqlt_orders
ORDER BY order_id;
