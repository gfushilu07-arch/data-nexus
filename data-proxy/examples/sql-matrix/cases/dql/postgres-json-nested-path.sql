-- case: SQLT-DQL-075
-- Purpose: Verify PostgreSQL extracts text from a nested JSON object path.
-- Expected: Selected customer names are reconstructed and extracted by primary key.
-- Dialect: postgres

SELECT customer_id,
       jsonb_build_object(
           'customer', jsonb_build_object('name', display_name)
       ) #>> '{customer,name}' AS nested_name
FROM sqlt_customers
WHERE customer_id IN (101, 202)
ORDER BY customer_id;
