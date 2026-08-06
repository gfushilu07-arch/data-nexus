-- fixture: SQLT-FIXTURE-MYSQL-PREPARED-SCHEMA-CHANGE
-- Purpose: Change a prepared wildcard query's result columns from a control connection.
-- Expected: The table gains one label column and its existing row receives a value.
-- Dialect: mysql

ALTER TABLE sqlt_prepared_schema
ADD COLUMN label VARCHAR(32) NOT NULL DEFAULT 'after-change';
