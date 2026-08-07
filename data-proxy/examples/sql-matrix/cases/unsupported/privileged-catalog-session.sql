-- case: SQLT-UNSUPPORTED-009
-- Purpose: Pin privileged system, session, and catalog access boundaries in both dialects.
-- Expected: Restricted direct users are denied and the gateway rejects every privileged capability step.
-- Dialect: mysql, postgres

-- @step global_setting mysql
SET GLOBAL max_connections = 151;
-- @step privileged_catalog mysql
SELECT User FROM mysql.user;
-- @step system_setting postgres
ALTER SYSTEM SET work_mem = '4MB';
-- @step session_role postgres
SET ROLE sqlt_missing_role;
-- @step privileged_catalog postgres
SELECT rolname FROM pg_authid;
