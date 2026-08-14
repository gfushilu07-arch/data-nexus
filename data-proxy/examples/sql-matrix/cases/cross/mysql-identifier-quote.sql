-- case: SQLT-XDQL-001
-- Purpose: Verify MySQL backtick identifiers are rewritten for a PostgreSQL backend.
-- Expected: Four customer IDs and names are returned in customer_id order.
-- Dialect: mysql

SELECT `customer_id` AS `id`, `display_name` AS `name`
FROM `sqlt_customers`
ORDER BY `customer_id`;
