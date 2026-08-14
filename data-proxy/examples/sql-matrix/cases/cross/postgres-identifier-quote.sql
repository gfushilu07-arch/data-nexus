-- case: SQLT-XDQL-001
-- Purpose: Verify PostgreSQL quoted identifiers are rewritten for a MySQL backend.
-- Expected: Four customer IDs and names are returned in customer_id order.
-- Dialect: postgres

SELECT "customer_id" AS "id", "display_name" AS "name"
FROM "sqlt_customers"
ORDER BY "customer_id";
