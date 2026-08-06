-- case: SQLT-DDL-049
-- Purpose: Drop an existing PostgreSQL sequence.
-- Expected: sqlt_ddl_sequence metadata and runtime state disappear.
-- Dialect: postgres

DROP SEQUENCE sqlt_ddl_sequence;
