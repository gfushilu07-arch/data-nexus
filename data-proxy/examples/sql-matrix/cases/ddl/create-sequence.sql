-- case: SQLT-DDL-047
-- Purpose: Create a PostgreSQL sequence with explicit bounds, increment, cache, and cycle policy.
-- Expected: sqlt_ddl_sequence has the declared parameters and has not produced a value.
-- Dialect: postgres

CREATE SEQUENCE sqlt_ddl_sequence
    AS BIGINT
    INCREMENT BY 5
    MINVALUE 10
    MAXVALUE 1000
    START WITH 10
    CACHE 3
    NO CYCLE;
