-- case: SQLT-CURSOR-006
-- Purpose: Continue a WITH HOLD cursor on the same frontend session after commit.
-- Expected: Row order and offset survive COMMIT until explicit CLOSE removes the cursor.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_hold_cursor NO SCROLL CURSOR WITH HOLD FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id;
-- @step fetch_before_commit
FETCH FORWARD 1 FROM sqlt_hold_cursor;
-- @step commit
COMMIT;
-- @step fetch_after_commit
FETCH FORWARD 2 FROM sqlt_hold_cursor;
-- @step fetch_rest
FETCH FORWARD ALL FROM sqlt_hold_cursor;
-- @step fetch_exhausted
FETCH FORWARD 1 FROM sqlt_hold_cursor;
-- @step close
CLOSE sqlt_hold_cursor;
-- @step after_close
FETCH FORWARD 1 FROM sqlt_hold_cursor;
