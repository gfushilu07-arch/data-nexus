-- case: SQLT-PGX-006
-- Purpose: Describe a statement and binary-result portal with catalog-backed column metadata.
-- Expected: RowDescription exposes table metadata and Execute returns binary bigint and text values.
-- Dialect: postgres

SELECT *
FROM sqlt_customers
WHERE customer_id = $1;
