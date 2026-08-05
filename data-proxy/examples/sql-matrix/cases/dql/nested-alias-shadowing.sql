-- case: SQLT-DQL-071
-- Purpose: Verify a nested relation alias shadows an identically named outer alias.
-- Expected: Both tenant 10 customers remain because the independent inner predicate is true.
-- Dialect: mysql, postgres

SELECT scoped.customer_id, scoped.display_name
FROM sqlt_customers AS scoped
WHERE scoped.tenant_id = 10
  AND EXISTS (
      SELECT 1
      FROM sqlt_orders AS scoped
      WHERE scoped.order_id = 1001
        AND scoped.customer_id = 101
  )
ORDER BY scoped.customer_id;
