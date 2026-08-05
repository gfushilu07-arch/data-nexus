-- fixture: SQLT-FIXTURE-POSTGRES-DDL-CHECK-CONFLICT
-- Purpose: Create a PostgreSQL table containing a value that violates a future positive check.
-- Expected: Adding the positive-value check is rejected.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NOT NULL
);

INSERT INTO sqlt_ddl_constraint (probe_id, probe_value)
VALUES (1, -1), (2, 10);
