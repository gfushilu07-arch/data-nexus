-- case: SQLT-CURSOR-002
-- Purpose: Fetch every remaining row and retain the exhausted cursor until explicit close.
-- Expected: FETCH ALL returns all rows, a later fetch is empty, and CLOSE succeeds.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_all_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id;
-- @step fetch_all
FETCH FORWARD ALL FROM sqlt_all_cursor;
-- @step fetch_exhausted
FETCH FORWARD ALL FROM sqlt_all_cursor;
-- @step close
CLOSE sqlt_all_cursor;
-- @step commit
COMMIT;
