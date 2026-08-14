#!/usr/bin/env bash
# Execute PostgreSQL named-cursor cases against direct Docker and the security-off gateway.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_CURSOR_RUN_ID:-cursor-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_CURSOR_CASE_FROM:-SQLT-CURSOR-001}"
CASE_TO="${SQLT_CURSOR_CASE_TO:-SQLT-CURSOR-008}"
COMPOSE_PROJECT="sqlt3ecursor-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
RESULTS="$RUN_DIR/results.jsonl"
FIXTURE_LOG="$RUN_DIR/logs/fixture.log"
GATEWAY_PID=""
RUN_LABEL=(--label "data-nexus.sql-matrix.run-id=$RUN_ID")

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output"
: >"$RESULTS"
: >"$FIXTURE_LOG"
cp "$ROOT/manifest.json" "$ROOT/capabilities.json" "$ROOT/cursor-oracles.json" "$RUN_DIR/"

cleanup() {
  [[ -z "$GATEWAY_PID" ]] || { kill "$GATEWAY_PID" 2>/dev/null || true; wait "$GATEWAY_PID" 2>/dev/null || true; }
  "${COMPOSE[@]}" logs --no-color >"$RUN_DIR/logs/compose.log" 2>&1 || true
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing curl" >&2; exit 1; }
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || { echo "SQLT-3E4 requires rustc 1.94.1" >&2; exit 1; }
python3 "$ROOT/validate.py"
python3 "$ROOT/select_cursor_cases.py" "$ROOT/manifest.json" \
  "$ROOT/cursor-oracles.json" "$CASE_FROM" "$CASE_TO" >"$RUN_DIR/selection.tsv"
[[ -s "$RUN_DIR/selection.tsv" ]] || { echo "cursor case selection is empty" >&2; exit 1; }

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

run_client() {
  local path="$1" case_id="$2" sql_file="$3" oracle_file="$4" mode="$5" output="$6"
  local port=25432 user=sqlt password=sqlt
  [[ "$path" == gateway ]] && { port=29089; user=root; password=root; }
  local args=(--case-id "$case_id" --sql "/matrix/cases/$sql_file" --oracle "/run/results/$oracle_file"
    --host host.docker.internal --port "$port" --user "$user" --password "$password" --path "$path")
  if [[ "$case_id" == SQLT-CURSOR-007 ]]; then
    args+=(--disconnect-after fetch_before_disconnect --disconnect-mode "$mode")
  fi
  docker run --rm "${RUN_LABEL[@]}" --add-host=host.docker.internal:host-gateway \
    -v "$ROOT:/matrix:ro" -v "$RUN_DIR:/run:ro" python:3.12-slim-bookworm \
    python /matrix/cursor_client.py "${args[@]}" >"$output" 2>"${output%.json}.err"
}

case_count=0
path_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  case_count=$((case_count + 1))
  oracle_name="${case_id}.oracle.json"
  python3 - "$ROOT/cursor-oracles.json" "$case_id" "$RUN_DIR/results/$oracle_name" <<'PY'
import json, sys
from pathlib import Path
value = json.load(open(sys.argv[1], encoding="utf-8"))["results"][sys.argv[2]]
Path(sys.argv[3]).write_text(json.dumps(value) + "\n", encoding="utf-8")
PY
  case_status=passed
  modes=(default)
  [[ "$case_id" == SQLT-CURSOR-007 ]] && modes=(terminate eof)
  for path in direct gateway; do
    for mode in "${modes[@]}"; do
      path_count=$((path_count + 1))
      load_fixture
      label="${case_id}-${path}"
      [[ "$mode" == default ]] || label="${label}-${mode}"
      output="$RUN_DIR/normalized-output/${label}.json"
      echo "==> $case_id [$dialect/$path/$mode]"
      if ! run_client "$path" "$case_id" "$sql_file" "$oracle_name" "$mode" "$output"; then
        case_status=failed
      fi
    done
  done
  python3 - "$RESULTS" "$case_id" "$dialect" "$sql_file" "$case_status" <<'PY'
import json, sys
with open(sys.argv[1], "a", encoding="utf-8") as out:
    out.write(json.dumps({"case_id": sys.argv[2], "dialect": sys.argv[3], "sql_file": sys.argv[4], "status": sys.argv[5]}, sort_keys=True) + "\n")
PY
  if [[ "$case_status" == passed ]]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi
done <"$RUN_DIR/selection.tsv"

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$path_count" "$pass_count" "$fail_count" "$CASE_FROM" "$CASE_TO" <<'PY'
import json, sys
from pathlib import Path
results = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
summary = {"case_dialect_executions": int(sys.argv[3]), "path_executions": int(sys.argv[4]),
           "passed": int(sys.argv[5]), "failed": int(sys.argv[6]), "results": results}
Path(sys.argv[2]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if sys.argv[7:] == ["SQLT-CURSOR-001", "SQLT-CURSOR-008"] and (summary["case_dialect_executions"] != 8 or summary["path_executions"] != 18):
    raise SystemExit(f"SQLT-3E4 selection mismatch: {summary['case_dialect_executions']} cases, {summary['path_executions']} paths")
if summary["failed"]:
    raise SystemExit(f"SQLT-3E4 failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3E4 passed: {summary['passed']} case/dialect and {summary['path_executions']} path executions")
PY
