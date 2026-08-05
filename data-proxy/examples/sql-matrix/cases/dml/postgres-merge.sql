-- case: SQLT-DML-039
-- Purpose: Verify PostgreSQL MERGE updates a match and inserts a non-match in one statement.
-- Expected: Target 4001 is updated, target 4011 is inserted, and affected rows is two.
-- Dialect: postgres

MERGE INTO sqlt_dml_targets AS target
USING (
    VALUES
        (4001::BIGINT, 101::BIGINT, 10, 'merge-updated', 98.00::NUMERIC, 'merged'),
        (4011::BIGINT, 201::BIGINT, 20, 'merge-inserted', 99.00::NUMERIC, 'merged')
) AS source (target_id, customer_id, tenant_id, description, amount, status)
ON target.target_id = source.target_id
WHEN MATCHED THEN
    UPDATE SET description = source.description,
               amount = source.amount,
               status = source.status
WHEN NOT MATCHED THEN
    INSERT (target_id, customer_id, tenant_id, description, amount, status)
    VALUES (source.target_id, source.customer_id, source.tenant_id,
            source.description, source.amount, source.status);
