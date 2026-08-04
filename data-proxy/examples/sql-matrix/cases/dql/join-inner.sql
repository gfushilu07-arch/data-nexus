-- case: SQLT-DQL-025
-- Purpose: Verify an explicit INNER JOIN with qualified projections and stable ordering.
-- Expected: All six orders are paired with their customer display names in order_id order.
-- Dialect: mysql, postgres

SELECT o.order_id, c.display_name
FROM sqlt_orders AS o
INNER JOIN sqlt_customers AS c ON c.customer_id = o.customer_id
ORDER BY o.order_id;
