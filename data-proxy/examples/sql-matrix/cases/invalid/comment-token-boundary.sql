-- case: SQLT-INVALID-017
-- Purpose: Verify line and block comments cannot turn embedded delimiters into executable SQL.
-- Expected: The expression returns 2 and the commented mutation text has no side effect.
-- Dialect: mysql, postgres

SELECT 1 /* ; INSERT INTO sqlt_mutations VALUES (9917, 'blocked', NULL, 'new'); */
       + 1 AS comment_boundary -- ; DELETE FROM sqlt_customers
;
