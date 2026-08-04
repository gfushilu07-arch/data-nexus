-- case: SQLT-DQL-061
-- Purpose: Verify MySQL JSON_EXTRACT and JSON_UNQUOTE field extraction.
-- Expected: Two JSON documents return their unquoted name values in name order.
-- Dialect: mysql

SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.name')) AS name,
       JSON_TYPE(payload) AS payload_type
FROM (
    SELECT CAST('{"name":"Ada","active":true}' AS JSON) AS payload
    UNION ALL
    SELECT CAST('{"name":"Grace","active":false}' AS JSON) AS payload
) AS values_table
ORDER BY name;
