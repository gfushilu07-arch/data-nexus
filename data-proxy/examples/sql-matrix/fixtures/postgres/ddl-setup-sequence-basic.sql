-- fixture: SQLT-FIXTURE-POSTGRES-DDL-SEQUENCE-BASIC
-- Purpose: Create an uncalled PostgreSQL sequence with deterministic parameters.
-- Expected: The sequence starts at 10 and has not produced a value.
-- Dialect: postgres

CREATE SEQUENCE sqlt_ddl_sequence
    AS BIGINT
    INCREMENT BY 5
    MINVALUE 10
    MAXVALUE 1000
    START WITH 10
    CACHE 3
    NO CYCLE;
