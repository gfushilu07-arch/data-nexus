-- case: SQLT-DQL-076
-- Purpose: Verify MySQL extracts unquoted text from a nested JSON object path.
-- Expected: Selected customer names are reconstructed and extracted by primary key.
-- Dialect: mysql

SELECT customer_id,
       JSON_UNQUOTE(JSON_EXTRACT(
           JSON_OBJECT('customer', JSON_OBJECT('name', display_name)),
           '$.customer.name'
       )) AS nested_name
FROM sqlt_customers
WHERE customer_id IN (101, 202)
ORDER BY customer_id;
