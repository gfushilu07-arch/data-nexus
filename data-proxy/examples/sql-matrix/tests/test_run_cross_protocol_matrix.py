from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "run-cross-protocol-matrix.sh"


class RunCrossProtocolMatrixTest(unittest.TestCase):
    def test_runner_uses_owned_resources_and_no_global_process_kill(self) -> None:
        script = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("pkill", script)
        self.assertIn('kill "$GATEWAY_PID"', script)
        self.assertIn('data-nexus.sql-matrix.run-id=$RUN_ID', script)
        self.assertIn('COMPOSE_PROJECT="sqlt4b1-$RUN_TOKEN"', script)
        self.assertIn('python3 "$ROOT/validate.py"', script)
        self.assertIn("acceptance_complete=false", script)
        self.assertIn("trap 'exit 130' INT", script)
        self.assertIn("trap 'exit 143' TERM", script)

    def test_runner_is_valid_for_system_bash(self) -> None:
        result = subprocess.run(
            ["/bin/bash", "-n", str(RUNNER)], check=False, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
