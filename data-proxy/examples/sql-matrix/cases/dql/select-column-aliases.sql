-- case: SQLT-DQL-005
-- Purpose: Verify explicit column projection and aliases from a fixture table.
-- Expected: Four customer rows are returned in customer_id order with stable aliases.
-- Dialect: mysql, postgres

SELECT customer_id AS id, display_name AS name
FROM sqlt_customers
ORDER BY customer_id;
