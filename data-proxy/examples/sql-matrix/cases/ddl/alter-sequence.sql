-- case: SQLT-DDL-048
-- Purpose: Alter PostgreSQL sequence parameters and reset its next-value baseline.
-- Expected: Parameters change and START/RESTART reset the uncalled baseline to 200.
-- Dialect: postgres

ALTER SEQUENCE sqlt_ddl_sequence
    INCREMENT BY 7
    MINVALUE 5
    MAXVALUE 2000
    START WITH 200
    RESTART WITH 200
    CACHE 5
    CYCLE;
