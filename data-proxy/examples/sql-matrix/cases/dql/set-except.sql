-- case: SQLT-DQL-044
-- Purpose: Verify EXCEPT removes customer IDs present in the second query operand.
-- Expected: Customer 102 is returned because it has no paid order.
-- Dialect: mysql, postgres

SELECT customer_id FROM sqlt_customers
EXCEPT
SELECT customer_id FROM sqlt_orders WHERE status = 'paid'
ORDER BY customer_id;
