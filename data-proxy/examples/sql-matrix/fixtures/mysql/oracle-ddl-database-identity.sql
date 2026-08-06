-- oracle: SQLT-ORACLE-MYSQL-DDL-DATABASE-IDENTITY-V1
-- Purpose: Confirm the direct and gateway actions execute as the restricted backend account.
-- Expected: The privilege account, login username, and selected database resolve to sqlt.
-- Dialect: mysql

SELECT CURRENT_USER(), SUBSTRING_INDEX(USER(), '@', 1), DATABASE();
