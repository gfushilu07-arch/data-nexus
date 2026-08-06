-- case: SQLT-PGX-005
-- Purpose: Resume one portal across bounded Execute pages.
-- Expected: Four one-row pages suspend and a final empty Execute completes the portal.
-- Dialect: postgres

SELECT customer_id
FROM sqlt_customers
ORDER BY customer_id;
