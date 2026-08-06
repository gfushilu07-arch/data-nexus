-- case: SQLT-CURSOR-007
-- Purpose: Release a partly consumed cursor on protocol Terminate and raw socket EOF.
-- Expected: No idle transaction remains and a new session can immediately reuse the name.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_session_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id;
-- @step fetch_before_disconnect
FETCH FORWARD 1 FROM sqlt_session_cursor;
-- @step cleanup_probe
SELECT COUNT(*) FROM pg_stat_activity
WHERE datname = current_database()
  AND state = 'idle in transaction'
  AND pid <> pg_backend_pid();
-- @step reuse_begin
BEGIN;
-- @step reuse_declare
DECLARE sqlt_session_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id DESC;
-- @step reuse_fetch
FETCH FORWARD ALL FROM sqlt_session_cursor;
-- @step reuse_close
CLOSE sqlt_session_cursor;
-- @step reuse_commit
COMMIT;
