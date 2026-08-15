from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "run-cross-protocol-dml-matrix.sh"


class RunCrossProtocolDmlMatrixTest(unittest.TestCase):
    def test_runner_uses_owned_resources_and_two_phase_resets(self) -> None:
        script = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("pkill", script)
        self.assertIn('kill "$GATEWAY_PID"', script)
        self.assertIn('data-nexus.sql-matrix.run-id=$RUN_ID', script)
        self.assertIn('COMPOSE_PROJECT="sqlt4b2-$RUN_TOKEN"', script)
        self.assertIn("tr '[:upper:]' '[:lower:]'", script)
        self.assertIn('python3 "$ROOT/validate.py"', script)
        self.assertIn('reset_backend "$backend" "$RUN_DIR/logs/$stem.backend-reset"', script)
        self.assertIn('reset_backend "$backend" "$RUN_DIR/logs/$stem.gateway-reset"', script)
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
