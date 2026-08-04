-- case: SQLT-DQL-041
-- Purpose: Verify UNION removes duplicate tenant identifiers across two relations.
-- Expected: Tenant IDs 10 and 20 are each returned exactly once.
-- Dialect: mysql, postgres

SELECT tenant_id FROM sqlt_customers
UNION
SELECT tenant_id FROM sqlt_orders
ORDER BY tenant_id;
