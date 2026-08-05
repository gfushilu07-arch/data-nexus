-- case: SQLT-DML-040
-- Purpose: Verify a PostgreSQL data-modifying CTE exposes deterministic updated rows.
-- Expected: Targets 4003 and 4004 gain one amount unit and are returned in primary-key order.
-- Dialect: postgres

WITH changed AS (
    UPDATE sqlt_dml_targets
    SET amount = COALESCE(amount, 0) + 1.00,
        status = 'cte-updated'
    WHERE target_id IN (4003, 4004)
    RETURNING target_id, description, amount, status
)
SELECT target_id, description, amount, status
FROM changed
ORDER BY target_id;
