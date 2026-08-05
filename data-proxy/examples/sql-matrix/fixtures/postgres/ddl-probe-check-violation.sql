-- fixture: SQLT-PROBE-POSTGRES-DDL-CHECK-VIOLATION
-- Purpose: Attempt a PostgreSQL row that violates the positive-value check.
-- Expected: The insert fails with the stable check-constraint error identity.
-- Dialect: postgres

INSERT INTO sqlt_ddl_constraint (probe_id, probe_value) VALUES (1, -1);
