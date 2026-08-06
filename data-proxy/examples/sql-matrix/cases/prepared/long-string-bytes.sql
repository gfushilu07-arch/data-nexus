-- case: SQLT-PRP-005
-- Purpose: Bind a long UTF-8 string and opaque bytes through binary length encoding.
-- Expected: Length, UTF-8 suffix, and hexadecimal bytes are returned without truncation.
-- Dialect: mysql

SELECT CHAR_LENGTH(%s) AS text_length,
       RIGHT(%s, 4) AS text_suffix,
       HEX(%s) AS bytes_hex
