-- case: SQLT-CURSOR-008
-- Purpose: Clean up a partly consumed cursor when its PostgreSQL backend session terminates.
-- Expected: The old stream fails, reconnect succeeds, and no idle transaction remains.
-- Dialect: postgres

-- @step begin
BEGIN;
-- @step declare
DECLARE sqlt_backend_cursor NO SCROLL CURSOR FOR
    SELECT pg_backend_pid()::bigint AS backend_pid, customer_id
    FROM sqlt_customers ORDER BY customer_id;
-- @step fetch_backend_pid
FETCH FORWARD 1 FROM sqlt_backend_cursor;
-- @step terminate_backend
-- @action backend_terminate
SELECT pg_terminate_backend(:backend_pid);
-- @step fetch_after_terminate
-- @action reconnect_after_backend_failure
FETCH FORWARD 1 FROM sqlt_backend_cursor;
-- @step cleanup_probe
SELECT COUNT(*) FROM pg_stat_activity
WHERE datname = current_database()
  AND state = 'idle in transaction'
  AND pid <> pg_backend_pid();
-- @step reuse_begin
BEGIN;
-- @step reuse_declare
DECLARE sqlt_backend_cursor NO SCROLL CURSOR FOR
    SELECT customer_id FROM sqlt_customers ORDER BY customer_id;
-- @step reuse_fetch
FETCH FORWARD ALL FROM sqlt_backend_cursor;
-- @step reuse_close
CLOSE sqlt_backend_cursor;
-- @step reuse_commit
COMMIT;
