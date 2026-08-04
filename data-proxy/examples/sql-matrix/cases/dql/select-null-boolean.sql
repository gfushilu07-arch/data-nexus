-- case: SQLT-DQL-006
-- Purpose: Verify NULL and boolean literals in a result projection.
-- Expected: One row is returned containing a NULL value and a dialect-native true value.
-- Dialect: mysql, postgres

SELECT NULL AS missing_value, TRUE AS enabled;
