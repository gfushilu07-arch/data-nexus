from __future__ import annotations

import hashlib
import importlib.util
import io
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sql_matrix_stream_summary", MATRIX_ROOT / "stream_summary.py"
)
assert SPEC and SPEC.loader
STREAM_SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STREAM_SUMMARY)


class TrackingBytesIO(io.BytesIO):
    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.max_requested = 0

    def read(self, size: int = -1) -> bytes:
        self.max_requested = max(self.max_requested, size)
        return super().read(size)


class StreamSummaryTest(unittest.TestCase):
    def test_empty_output(self) -> None:
        summary = STREAM_SUMMARY.summarize_stream(io.BytesIO(b""), chunk_bytes=4)
        self.assertEqual(summary["bytes"], 0)
        self.assertEqual(summary["lines"], 0)
        self.assertEqual(summary["max_line_bytes"], 0)
        self.assertFalse(summary["ends_with_lf"])
        self.assertIsNone(summary["first_line_sha256"])
        self.assertIsNone(summary["last_line_sha256"])

    def test_chunk_boundaries_preserve_line_hashes(self) -> None:
        value = b"alpha\nbeta-beta\ngamma\n"
        summary = STREAM_SUMMARY.summarize_stream(io.BytesIO(value), chunk_bytes=3)
        self.assertEqual(summary["bytes"], len(value))
        self.assertEqual(summary["lines"], 3)
        self.assertEqual(summary["max_line_bytes"], 9)
        self.assertTrue(summary["ends_with_lf"])
        self.assertEqual(summary["sha256"], hashlib.sha256(value).hexdigest())
        self.assertEqual(
            summary["first_line_sha256"], hashlib.sha256(b"alpha").hexdigest()
        )
        self.assertEqual(
            summary["last_line_sha256"], hashlib.sha256(b"gamma").hexdigest()
        )

    def test_long_line_is_read_with_bounded_chunks(self) -> None:
        value = (b"x" * 200_000) + b"\n"
        source = TrackingBytesIO(value)
        summary = STREAM_SUMMARY.summarize_stream(source, chunk_bytes=65536)
        self.assertLessEqual(source.max_requested, 65536)
        self.assertEqual(summary["lines"], 1)
        self.assertEqual(summary["max_line_bytes"], 200_000)
        self.assertEqual(
            summary["first_line_sha256"], hashlib.sha256(value[:-1]).hexdigest()
        )

    def test_missing_final_lf_finishes_last_line(self) -> None:
        summary = STREAM_SUMMARY.summarize_stream(io.BytesIO(b"one\ntwo"), chunk_bytes=4)
        self.assertEqual(summary["lines"], 2)
        self.assertEqual(summary["max_line_bytes"], 3)
        self.assertFalse(summary["ends_with_lf"])
        self.assertEqual(
            summary["last_line_sha256"], hashlib.sha256(b"two").hexdigest()
        )

    def test_non_positive_chunk_size_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be positive"):
            STREAM_SUMMARY.summarize_stream(io.BytesIO(b"value"), chunk_bytes=0)


if __name__ == "__main__":
    unittest.main()
