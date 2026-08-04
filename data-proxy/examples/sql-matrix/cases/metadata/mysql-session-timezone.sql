-- case: SQLT-META-011
-- Purpose: Verify MySQL session time-zone assignment and inspection.
-- Expected: The follow-up query returns +00:00 without changing global configuration.
-- Dialect: mysql

SET SESSION time_zone = '+00:00';
SELECT @@session.time_zone;
