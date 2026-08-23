-- fixture: SQLT-FIXTURE-POSTGRES-CLEANUP
-- Purpose: Remove every SQLT object before rebuilding the PostgreSQL fixture.
-- Expected: The public schema contains none of the versioned fixture and DDL probe tables.
-- Dialect: postgres

DROP VIEW IF EXISTS sqlt_ddl_view;
DROP TABLE IF EXISTS sqlt_dml_targets;
DROP TABLE IF EXISTS sqlt_orders;
DROP TABLE IF EXISTS sqlt_customers;
DROP TABLE IF EXISTS sqlt_mutations;
DROP TABLE IF EXISTS sqlt_ddl_oracle;
DROP TABLE IF EXISTS sqlt_ddl_probe;
DROP TABLE IF EXISTS sqlt_ddl_create;
DROP TABLE IF EXISTS sqlt_ddl_if_not_exists;
DROP TABLE IF EXISTS sqlt_ddl_duplicate;
DROP TABLE IF EXISTS sqlt_ddl_alter;
DROP TABLE IF EXISTS sqlt_ddl_renamed;
DROP TABLE IF EXISTS sqlt_ddl_truncate;
DROP TABLE IF EXISTS sqlt_ddl_missing;
DROP TABLE IF EXISTS sqlt_ddl_temp;
DROP TABLE IF EXISTS sqlt_ddl_constraint;
DROP TABLE IF EXISTS sqlt_ddl_parent;
DROP TABLE IF EXISTS sqlt_ddl_column;
DROP TABLE IF EXISTS sqlt_ddl_index;
DROP TABLE IF EXISTS sqlt_ddl_view_source;
DROP TABLE IF EXISTS sqlt_tcl_ddl;
DROP SCHEMA IF EXISTS sqlt_ddl_schema CASCADE;
DROP SEQUENCE IF EXISTS sqlt_ddl_sequence;
-- SQLT-5C-b governance ticket-case tables
DROP TABLE IF EXISTS sqlt_gov_ticket_t CASCADE;
DROP TABLE IF EXISTS sqlt_gov_ticket_reuse_t CASCADE;
