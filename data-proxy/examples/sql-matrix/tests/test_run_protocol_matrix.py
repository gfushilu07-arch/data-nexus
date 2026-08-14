from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "run-protocol-matrix.sh"


class RunProtocolMatrixTest(unittest.TestCase):
    def test_formal_aggregation_avoids_empty_array_expansion(self) -> None:
        script = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("AGGREGATE_FILTER", script)
        self.assertIn('if ((FILTERED)); then', script)
        self.assertIn('--run-id "$RUN_ID" --filtered "${SUMMARY_ARGS[@]}"', script)
        self.assertIn('--run-id "$RUN_ID" "${SUMMARY_ARGS[@]}"', script)

    def test_runner_is_valid_for_system_bash(self) -> None:
        result = subprocess.run(
            ["/bin/bash", "-n", str(RUNNER)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
