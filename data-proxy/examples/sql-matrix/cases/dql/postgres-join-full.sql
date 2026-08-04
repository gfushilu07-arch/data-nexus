-- case: SQLT-DQL-028
-- Purpose: Verify PostgreSQL FULL OUTER JOIN preserves unmatched rows from both inputs.
-- Expected: One matched row and one unmatched row from each filtered input are returned.
-- Dialect: postgres

SELECT c.customer_id, o.order_id
FROM (
    SELECT customer_id
    FROM sqlt_customers
    WHERE customer_id IN (101, 102)
) AS c
FULL OUTER JOIN (
    SELECT order_id, customer_id
    FROM sqlt_orders
    WHERE order_id IN (1001, 2003)
) AS o ON o.customer_id = c.customer_id
ORDER BY COALESCE(c.customer_id, o.customer_id), o.order_id;
