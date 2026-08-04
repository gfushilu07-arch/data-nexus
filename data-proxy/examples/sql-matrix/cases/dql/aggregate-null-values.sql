-- case: SQLT-DQL-021
-- Purpose: Verify that COUNT(column) excludes NULL while COUNT(*) includes every row.
-- Expected: total_count is 4 and email_count is 3 for the customer fixture.
-- Dialect: mysql, postgres

SELECT COUNT(*) AS total_count, COUNT(email) AS email_count
FROM sqlt_customers;
