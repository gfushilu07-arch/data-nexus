-- oracle: SQLT-ORACLE-POSTGRES-DDL-V1
-- Purpose: Exercise PostgreSQL create, alter, insert, metadata inspection, and drop behavior.
-- Expected: The added column is visible before drop and the probe table is then removed.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_oracle (
    probe_id INTEGER PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
ALTER TABLE sqlt_ddl_oracle ADD COLUMN probe_note VARCHAR(128);
INSERT INTO sqlt_ddl_oracle (probe_id, probe_name, probe_note)
VALUES (1, 'ddl oracle', 'added column');
SELECT probe_id, probe_name, probe_note
FROM sqlt_ddl_oracle
ORDER BY probe_id;
DROP TABLE sqlt_ddl_oracle;
