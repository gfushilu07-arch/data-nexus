-- case: SQLT-CURSOR-001
-- Purpose: Verify PostgreSQL forward named-cursor declaration, fetch, and close.
-- Expected: Allow returns two ordered windows and closes the cursor without extra rows.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_order_cursor NO SCROLL CURSOR FOR
    SELECT order_id, customer_id, total_amount
    FROM sqlt_orders
    ORDER BY order_id;
-- @step fetch_first
FETCH FORWARD 2 FROM sqlt_order_cursor;
-- @step fetch_second
FETCH FORWARD 2 FROM sqlt_order_cursor;
-- @step close
CLOSE sqlt_order_cursor;
-- @step commit
COMMIT;
-- @step after_close
FETCH FORWARD 1 FROM sqlt_order_cursor;
