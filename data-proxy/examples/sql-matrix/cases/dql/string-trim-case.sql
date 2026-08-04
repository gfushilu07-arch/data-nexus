-- case: SQLT-DQL-051
-- Purpose: Verify TRIM and case conversion over a deterministic literal expression.
-- Expected: One row returns the normalized string `DATA NEXUS`.
-- Dialect: mysql, postgres

SELECT UPPER(TRIM('  Data Nexus  ')) AS normalized_name;
