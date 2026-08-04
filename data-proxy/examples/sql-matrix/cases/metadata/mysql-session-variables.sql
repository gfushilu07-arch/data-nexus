-- case: SQLT-META-009
-- Purpose: Verify deterministic MySQL session variables can be inspected.
-- Expected: Allow returns autocommit, transaction isolation, and character set values.
-- Dialect: mysql

SELECT @@session.autocommit,
       @@session.transaction_isolation,
       @@session.character_set_client;
