-- fixture: SQLT-FIXTURE-POSTGRES-DDL-SEQUENCE-CALLED
-- Purpose: Create a PostgreSQL sequence and consume its deterministic first value.
-- Expected: nextval returns 10 while pg_sequences persists cached-block upper bound 20.
-- Dialect: postgres

CREATE SEQUENCE sqlt_ddl_sequence
    AS BIGINT
    INCREMENT BY 5
    MINVALUE 10
    MAXVALUE 1000
    START WITH 10
    CACHE 3
    NO CYCLE;

SELECT nextval('sqlt_ddl_sequence');
