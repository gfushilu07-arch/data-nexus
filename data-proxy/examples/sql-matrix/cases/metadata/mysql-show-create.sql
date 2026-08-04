-- case: SQLT-META-006
-- Purpose: Verify MySQL canonical CREATE TABLE metadata retrieval.
-- Expected: Allow returns one CREATE TABLE definition for sqlt_customers.
-- Dialect: mysql

SHOW CREATE TABLE sqlt_customers;
