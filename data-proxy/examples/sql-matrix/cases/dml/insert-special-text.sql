-- case: SQLT-DML-008
-- Purpose: Verify MySQL quote escaping, a literal backslash, and UTF-8 text in INSERT.
-- Expected: After selecting utf8mb4 for the session, the description contains quote ' slash \ and UTF-8 中文 exactly once each.
-- Dialect: mysql

SET NAMES utf8mb4;

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3007, 'quote '' slash \\ utf8 中文', 50.00, 'text');
