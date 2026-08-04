-- case: SQLT-DQL-060
-- Purpose: Verify PostgreSQL JSONB field extraction and type inspection.
-- Expected: Two JSON documents return their name field and JSONB type.
-- Dialect: postgres

SELECT payload ->> 'name' AS name,
       jsonb_typeof(payload) AS payload_type
FROM (
    VALUES
        ('{"name":"Ada","active":true}'::jsonb),
        ('{"name":"Grace","active":false}'::jsonb)
) AS values_table(payload)
ORDER BY name;
