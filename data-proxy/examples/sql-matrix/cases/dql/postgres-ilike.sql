-- case: SQLT-DQL-065
-- Purpose: Verify PostgreSQL ILIKE performs case-insensitive pattern matching.
-- Expected: Customers whose display names contain the letter A are returned by primary key.
-- Dialect: postgres

SELECT customer_id, display_name
FROM sqlt_customers
WHERE display_name ILIKE '%A%'
ORDER BY customer_id;
