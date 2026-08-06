from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("extended_client", ROOT / "extended_client.py")
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class ExtendedClientTest(unittest.TestCase):
    def test_reads_named_statement_sections(self) -> None:
        statements = CLIENT.read_statements(ROOT / "cases/extended/sync-error-recovery.sql")
        self.assertEqual(set(statements), {"failing", "ignored", "recovered"})
        self.assertIn("1 / $1", statements["failing"])

    def test_parses_binary_bigint_data_row(self) -> None:
        body = struct.pack("!h", 1) + struct.pack("!i", 8) + struct.pack("!q", 101)
        columns = [{"format_code": 1, "type_oid": 20}]
        self.assertEqual(CLIENT.data_row(body, columns), ["101"])

    def test_bind_preserves_protocol_null(self) -> None:
        frame = CLIENT.bind("p", "s", [None])
        self.assertIn(struct.pack("!i", -1), frame)

    def test_error_recovery_requires_queued_messages_to_be_ignored(self) -> None:
        events = [
            {"tag": "ParseComplete"},
            {"tag": "ErrorResponse", "sqlstate": "22012"},
            {"tag": "ReadyForQuery", "status": "I"},
        ]
        self.assertTrue(CLIENT.ignored_messages_absent(events))

        events.insert(2, {"tag": "ParseComplete"})
        self.assertFalse(CLIENT.ignored_messages_absent(events))

    def test_error_recovery_allows_completions_before_error(self) -> None:
        events = [
            {"tag": "ParseComplete"},
            {"tag": "BindComplete"},
            {"tag": "ErrorResponse", "sqlstate": "22012"},
            {"tag": "ReadyForQuery", "status": "I"},
        ]
        self.assertTrue(CLIENT.ignored_messages_absent(events))


if __name__ == "__main__":
    unittest.main()
