-- case: SQLT-INVALID-006
-- Purpose: Verify an unqualified duplicate column reference is rejected as ambiguous.
-- Expected: Column resolution fails and fixture state is unchanged.
-- Dialect: mysql, postgres

SELECT customer_id
FROM sqlt_customers
JOIN sqlt_orders
  ON sqlt_customers.customer_id = sqlt_orders.customer_id;
