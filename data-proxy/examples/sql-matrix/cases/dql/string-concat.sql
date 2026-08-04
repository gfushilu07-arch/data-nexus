-- case: SQLT-DQL-049
-- Purpose: Verify portable string concatenation with an explicit separator.
-- Expected: Customer display names are prefixed with their tenant and ordered by ID.
-- Dialect: mysql, postgres

SELECT customer_id,
       CONCAT(display_name, '-', tenant_id) AS label
FROM sqlt_customers
ORDER BY customer_id;
