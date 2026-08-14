#!/usr/bin/env bash
# Execute PostgreSQL extended-wire cases against direct Docker and the security-off gateway.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_EXTENDED_RUN_ID:-extended-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_EXTENDED_CASE_FROM:-SQLT-PGX-001}"
CASE_TO="${SQLT_EXTENDED_CASE_TO:-SQLT-PGX-008}"
COMPOSE_PROJECT="sqlt3epgx-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
RESULTS="$RUN_DIR/results.jsonl"
FIXTURE_LOG="$RUN_DIR/logs/fixture.log"
GATEWAY_PID=""
RUN_LABEL=(--label "data-nexus.sql-matrix.run-id=$RUN_ID")

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output"
: >"$RESULTS"
: >"$FIXTURE_LOG"
cp "$ROOT/manifest.json" "$ROOT/capabilities.json" "$ROOT/extended-oracles.json" "$RUN_DIR/"

cleanup() {
  [[ -z "$GATEWAY_PID" ]] || { kill "$GATEWAY_PID" 2>/dev/null || true; wait "$GATEWAY_PID" 2>/dev/null || true; }
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing curl" >&2; exit 1; }
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || { echo "SQLT-3E3 requires rustc 1.94.1" >&2; exit 1; }
python3 "$ROOT/validate.py"
python3 "$ROOT/select_extended_cases.py" "$ROOT/manifest.json" \
  "$ROOT/extended-oracles.json" "$CASE_FROM" "$CASE_TO" >"$RUN_DIR/selection.tsv"
[[ -s "$RUN_DIR/selection.tsv" ]] || { echo "extended case selection is empty" >&2; exit 1; }

"${COMPOSE[@]}" up -d postgres >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  "${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null | grep -q accepting && break
  sleep 2
done
"${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt

GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == 1 || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && cargo build -p data-proxy --bin proxy) >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" | tee "$RUN_DIR/logs/cargo-build.log"
fi
"$GATEWAY_BIN" daemon -c "$ROOT/fixtures/gateway-config.toml" >"$RUN_DIR/logs/gateway.log" 2>&1 & GATEWAY_PID=$!
printf '%s\n' "$GATEWAY_PID" >"$RUN_DIR/gateway.pid"
for _ in $(seq 1 90); do
  curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null && break
  kill -0 "$GATEWAY_PID" 2>/dev/null || { echo "gateway exited early" >&2; exit 1; }
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

run_psql() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 -U sqlt -d sqlt <"$1"
}

load_fixture() {
  run_psql "$ROOT/fixtures/postgres/cleanup.sql" >>"$FIXTURE_LOG" 2>&1
  run_psql "$ROOT/fixtures/postgres/schema.sql" >>"$FIXTURE_LOG" 2>&1
  run_psql "$ROOT/fixtures/postgres/seed.sql" >>"$FIXTURE_LOG" 2>&1
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  case_count=$((case_count + 1))
  oracle_file="$RUN_DIR/results/${case_id}.oracle.json"
  python3 - "$ROOT/extended-oracles.json" "$case_id" "$oracle_file" <<'PY'
import json, sys
from pathlib import Path
value = json.load(open(sys.argv[1], encoding="utf-8"))["results"][sys.argv[2]]
Path(sys.argv[3]).write_text(json.dumps(value) + "\n", encoding="utf-8")
PY
  case_status=passed
  for path in direct gateway; do
    load_fixture
    port=25432 user=sqlt password=sqlt
    [[ "$path" == gateway ]] && { port=29089; user=root; password=root; }
    output="$RUN_DIR/normalized-output/${case_id}-${path}.json"
    if ! docker run --rm "${RUN_LABEL[@]}" --add-host=host.docker.internal:host-gateway \
      -v "$ROOT:/matrix:ro" -v "$RUN_DIR:/run:ro" python:3.12-slim-bookworm \
      python /matrix/extended_client.py --case-id "$case_id" --sql "/matrix/cases/$sql_file" \
      --oracle "/run/results/${case_id}.oracle.json" --host host.docker.internal --port "$port" \
      --user "$user" --password "$password" >"$output" 2>"${output%.json}.err"; then
      case_status=failed
    fi
  done
  python3 - "$RESULTS" "$case_id" "$dialect" "$sql_file" "$case_status" <<'PY'
import json, sys
with open(sys.argv[1], "a", encoding="utf-8") as out:
    out.write(json.dumps({"case_id": sys.argv[2], "dialect": sys.argv[3], "sql_file": sys.argv[4], "status": sys.argv[5]}, sort_keys=True) + "\n")
PY
  if [[ "$case_status" == passed ]]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi
done <"$RUN_DIR/selection.tsv"

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json, sys
from pathlib import Path
results = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
summary = {"case_dialect_executions": int(sys.argv[3]), "path_executions": int(sys.argv[3]) * 2,
           "passed": int(sys.argv[4]), "failed": int(sys.argv[5]), "results": results}
Path(sys.argv[2]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if summary["failed"]:
    raise SystemExit(f"SQLT-3E3 failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3E3 passed: {summary['passed']} case/dialect and {summary['path_executions']} path executions")
PY
