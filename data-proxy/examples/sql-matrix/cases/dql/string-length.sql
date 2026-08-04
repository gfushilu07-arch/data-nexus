-- case: SQLT-DQL-050
-- Purpose: Verify character length and substring functions on customer names.
-- Expected: Each row returns its name length and first two characters in ID order.
-- Dialect: mysql, postgres

SELECT customer_id,
       CHAR_LENGTH(display_name) AS name_length,
       SUBSTRING(display_name FROM 1 FOR 2) AS name_prefix
FROM sqlt_customers
ORDER BY customer_id;
