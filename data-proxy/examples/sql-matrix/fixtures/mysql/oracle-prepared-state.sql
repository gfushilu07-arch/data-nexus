-- oracle: SQLT-ORACLE-MYSQL-PREPARED-STATE-V1
-- Purpose: Inspect prepared fixture mutations and schema-change table visibility.
-- Expected: Emit stable mutation, table, and column counts after each prepared case.
-- Dialect: mysql

SELECT 'mutation_rows', COUNT(*) FROM sqlt_mutations;
SELECT 'prepared_table', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'sqlt_prepared_schema';
SELECT 'prepared_columns', COUNT(*)
FROM information_schema.columns
WHERE table_schema = DATABASE() AND table_name = 'sqlt_prepared_schema';
