-- case: SQLT-DQL-008
-- Purpose: Verify duplicate elimination with DISTINCT and deterministic ordering.
-- Expected: The statuses paid, pending, and refunded are each returned exactly once.
-- Dialect: mysql, postgres

SELECT DISTINCT status
FROM sqlt_orders
ORDER BY status;
