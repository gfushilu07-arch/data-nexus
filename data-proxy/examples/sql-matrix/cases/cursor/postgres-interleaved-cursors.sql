-- case: SQLT-CURSOR-003
-- Purpose: Interleave two independently filtered named cursors in one transaction.
-- Expected: Each cursor preserves its own offset, rows, metadata, and close lifecycle.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare_a
DECLARE sqlt_cursor_a NO SCROLL CURSOR FOR
    SELECT customer_id, display_name FROM sqlt_customers
    WHERE tenant_id = 10 ORDER BY customer_id;
-- @step declare_b
DECLARE sqlt_cursor_b NO SCROLL CURSOR FOR
    SELECT customer_id, display_name FROM sqlt_customers
    WHERE tenant_id = 20 ORDER BY customer_id DESC;
-- @step fetch_a_first
FETCH FORWARD 1 FROM sqlt_cursor_a;
-- @step fetch_b_first
FETCH FORWARD 1 FROM sqlt_cursor_b;
-- @step fetch_a_rest
FETCH FORWARD ALL FROM sqlt_cursor_a;
-- @step close_a
CLOSE sqlt_cursor_a;
-- @step fetch_b_rest
FETCH FORWARD ALL FROM sqlt_cursor_b;
-- @step close_b
CLOSE sqlt_cursor_b;
-- @step commit
COMMIT;
