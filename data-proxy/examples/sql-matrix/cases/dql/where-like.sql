-- case: SQLT-DQL-012
-- Purpose: Verify case-sensitive prefix matching with LIKE on fixture text.
-- Expected: Customers whose display_name starts with A or E are returned in ID order.
-- Dialect: mysql, postgres

SELECT customer_id, display_name
FROM sqlt_customers
WHERE display_name LIKE 'A%' OR display_name LIKE 'E%'
ORDER BY customer_id;
