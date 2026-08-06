-- case: SQLT-INVALID-019
-- Purpose: Verify an overlong table identifier has deterministic vendor behavior without catalog mutation.
-- Expected: Name resolution fails with a stable vendor error and leaves the fixture unchanged.
-- Dialect: mysql, postgres

SELECT *
FROM sqlt_identifier_abcdefghijklmnopqrstuvwxyz_abcdefghijklmnopqrstuvwxyz_0123456789;
