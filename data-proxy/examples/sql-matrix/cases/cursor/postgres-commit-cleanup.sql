-- case: SQLT-CURSOR-005
-- Purpose: Verify that a non-hold cursor is removed when its transaction commits.
-- Expected: FETCH and CLOSE fail with 34000 after COMMIT, then the name can be reused.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_commit_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id;
-- @step fetch_before_commit
FETCH FORWARD 1 FROM sqlt_commit_cursor;
-- @step commit
COMMIT;
-- @step fetch_after_commit
FETCH FORWARD 1 FROM sqlt_commit_cursor;
-- @step close_after_commit
CLOSE sqlt_commit_cursor;
-- @step reuse_begin
BEGIN;
-- @step reuse_declare
DECLARE sqlt_commit_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id DESC;
-- @step reuse_fetch
FETCH FORWARD 1 FROM sqlt_commit_cursor;
-- @step reuse_close
CLOSE sqlt_commit_cursor;
-- @step reuse_commit
COMMIT;
