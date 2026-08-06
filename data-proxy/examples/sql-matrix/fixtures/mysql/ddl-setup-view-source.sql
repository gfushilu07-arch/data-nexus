-- fixture: SQLT-FIXTURE-MYSQL-DDL-VIEW-SOURCE
-- Purpose: Create a MySQL source table without the view under test.
-- Expected: The source columns and rows support deterministic view creation.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_view_source (
    source_id INTEGER NOT NULL,
    source_name VARCHAR(32) NOT NULL
);

INSERT INTO sqlt_ddl_view_source (source_id, source_name)
VALUES (1, 'alpha'), (2, 'beta');
