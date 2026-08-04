-- case: SQLT-DQL-009
-- Purpose: Verify a conjunctive WHERE predicate over tenant and decimal columns.
-- Expected: Only tenant 20 orders with total_amount greater than 40 are returned.
-- Dialect: mysql, postgres

SELECT order_id, total_amount
FROM sqlt_orders
WHERE tenant_id = 20 AND total_amount > 40
ORDER BY order_id;
