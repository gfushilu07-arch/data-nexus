-- oracle: SQLT-ORACLE-POSTGRES-TCL-STATE-V1
-- Purpose: Inspect all TCL mutation rows and transactional DDL visibility after a case.
-- Expected: Ordered mutation rows followed by one sqlt_tcl_ddl existence row.
-- Dialect: postgres

SELECT mutation_id, description, amount::text, status
FROM sqlt_mutations
WHERE mutation_id BETWEEN 9000 AND 9299
ORDER BY mutation_id;
SELECT 'ddl_table', COUNT(*)
FROM information_schema.tables
WHERE table_schema = current_schema() AND table_name = 'sqlt_tcl_ddl';
