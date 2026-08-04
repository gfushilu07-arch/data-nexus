-- case: SQLT-CURSOR-001
-- Purpose: Verify PostgreSQL forward named-cursor declaration, fetch, and close.
-- Expected: Allow returns two ordered windows and closes the cursor without extra rows.
-- Dialect: postgres

BEGIN;
DECLARE sqlt_order_cursor NO SCROLL CURSOR FOR
    SELECT order_id, customer_id, total_amount
    FROM sqlt_orders
    ORDER BY order_id;
FETCH FORWARD 2 FROM sqlt_order_cursor;
FETCH FORWARD 2 FROM sqlt_order_cursor;
CLOSE sqlt_order_cursor;
COMMIT;
