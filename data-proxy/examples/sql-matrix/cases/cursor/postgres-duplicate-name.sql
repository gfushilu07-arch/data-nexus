-- case: SQLT-CURSOR-004
-- Purpose: Recover from a duplicate cursor name and reuse the name after close.
-- Expected: Duplicate DECLARE returns 42P03, savepoint recovery preserves the original cursor.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_duplicate_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id;
-- @step savepoint
SAVEPOINT before_duplicate;
-- @step duplicate
DECLARE sqlt_duplicate_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers WHERE FALSE;
-- @step recover
ROLLBACK TO SAVEPOINT before_duplicate;
-- @step fetch_original
FETCH FORWARD 1 FROM sqlt_duplicate_cursor;
-- @step close_original
CLOSE sqlt_duplicate_cursor;
-- @step redeclare
DECLARE sqlt_duplicate_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id DESC;
-- @step fetch_redeclared
FETCH FORWARD 1 FROM sqlt_duplicate_cursor;
-- @step close_redeclared
CLOSE sqlt_duplicate_cursor;
-- @step commit
COMMIT;
