-- case: SQLT-DQL-085
-- Purpose: Verify a single query field can carry one mebibyte without truncation.
-- Expected: One row contains exactly 1,048,576 lowercase x bytes followed by the client LF.
-- Dialect: mysql, postgres

SELECT REPEAT('x', 1048576);
