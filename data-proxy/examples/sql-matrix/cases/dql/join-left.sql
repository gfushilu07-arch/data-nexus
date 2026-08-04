-- case: SQLT-DQL-026
-- Purpose: Verify LEFT JOIN null extension when the filtered right relation has no match.
-- Expected: All customers are returned and only customer 201 has refunded order 2002.
-- Dialect: mysql, postgres

SELECT c.customer_id, o.order_id
FROM sqlt_customers AS c
LEFT JOIN sqlt_orders AS o
    ON o.customer_id = c.customer_id AND o.status = 'refunded'
ORDER BY c.customer_id, o.order_id;
