-- case: SQLT-SEC-001
-- Purpose: Verify simultaneous sensitive-column masking and tenant row filtering.
-- Expected: Rewrites hide email values or foreign-tenant rows; deny returns no data.
-- Dialect: mysql, postgres

SELECT customer_id, tenant_id, email, display_name
FROM sqlt_customers
ORDER BY customer_id;
