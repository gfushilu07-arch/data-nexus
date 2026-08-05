#!/usr/bin/env bash
# Execute canonical DDL cases against fixed Docker backends and the security-off gateway.
# Every case/path starts from a rebuilt schema baseline and writes artifacts externally.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_DDL_RUN_ID:-ddl-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_DDL_CASE_FROM:-SQLT-DDL-001}"
CASE_TO="${SQLT_DDL_CASE_TO:-SQLT-DDL-010}"
COMPOSE_PROJECT="sqlt3dddl-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
RESULTS="$RUN_DIR/results.jsonl"
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_LOG="$RUN_DIR/logs/gateway.log"
GATEWAY_PID=""

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/normalized-output" "$RUN_DIR/results"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/ddl-oracles.json" "$RUN_DIR/ddl-oracles.json"

cleanup() {
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing required command: docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing required command: python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing required command: curl" >&2; exit 1; }
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-3D requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
python3 "$ROOT/validate.py"

echo "==> starting fixed-version SQLT-3D Docker backends"
"${COMPOSE[@]}" up -d >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then break; fi
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent
"${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt

echo "==> preparing security-off gateway"
GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == "1" || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && cargo build -p data-proxy --bin proxy) \
    >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" | tee "$RUN_DIR/logs/cargo-build.log"
fi
[[ -x "$GATEWAY_BIN" ]] || { echo "gateway binary not found: $GATEWAY_BIN" >&2; exit 1; }
"$GATEWAY_BIN" daemon -c "$GATEWAY_CONFIG" >"$GATEWAY_LOG" 2>&1 &
GATEWAY_PID=$!
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "gateway exited early; see $GATEWAY_LOG" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

run_mysql_direct() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

run_postgres_direct() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

run_mysql_gateway() {
  docker run --rm -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
    mysql --batch --raw --skip-column-names --default-character-set=utf8mb4 \
    --ssl-mode=DISABLED -h host.docker.internal -P 29088 -uroot -proot <"$1"
}

run_postgres_gateway() {
  docker run --rm -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
    env PGPASSWORD=root psql -X -q -v ON_ERROR_STOP=1 -v VERBOSITY=verbose \
    -P null=NULL -A -t -F $'\t' -h host.docker.internal -p 29089 -U root -d sqlt <"$1"
}

run_direct() {
  local dialect="$1"
  local sql_file="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql_direct "$sql_file"
  else
    run_postgres_direct "$sql_file"
  fi
}

reset_case() {
  local dialect="$1"
  local setup="$2"
  run_direct "$dialect" "$ROOT/fixtures/$dialect/cleanup.sql" >/dev/null
  if [[ -n "$setup" ]]; then
    run_direct "$dialect" "$ROOT/$setup" >/dev/null
  fi
}

catalog_snapshot() {
  local dialect="$1"
  local destination="$2"
  local query
  query="$(python3 - "$ROOT/ddl-oracles.json" "$dialect" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8"))["catalog_queries"][sys.argv[2]])
PY
)"
  run_direct "$dialect" "$ROOT/$query" >"$destination"
  python3 "$ROOT/normalize.py" "$destination" "$destination.normalized"
  mv "$destination.normalized" "$destination"
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys
from pathlib import Path

results, case_id, dialect, path, status, execution, before, after, error = sys.argv[1:]
with Path(results).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": dialect,
        "path": path,
        "status": status,
        "execution": execution,
        "before_catalog": before,
        "after_catalog": after,
        "error": error,
    }, sort_keys=True) + "\n")
PY
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  sql_path="$ROOT/cases/$sql_file"
  oracle="$RUN_DIR/results/${case_id}-${dialect}.oracle.json"
  python3 - "$ROOT/ddl-oracles.json" "$case_id" "$dialect" "$oracle" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, destination = sys.argv[1:]
value = json.load(open(source, encoding="utf-8"))["results"][case_id][dialect]
Path(destination).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  expected_result="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["result"])' "$oracle")"
  setup="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("setup") or "")' "$oracle")"
  unchanged="$(python3 -c 'import json,sys; print("yes" if json.load(open(sys.argv[1])).get("unchanged") else "no")' "$oracle")"
  expected_state="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-state.tsv"
  expected_error="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-error.tsv"
  python3 - "$oracle" "$expected_state" "$expected_error" <<'PY'
import json
import sys
from pathlib import Path

value = json.load(open(sys.argv[1], encoding="utf-8"))
Path(sys.argv[2]).write_text(value["state"], encoding="utf-8")
Path(sys.argv[3]).write_text(value.get("error", ""), encoding="utf-8")
PY

  for path in direct gateway; do
    case_count=$((case_count + 1))
    echo "==> $case_id [$dialect/$path]"
    reset_case "$dialect" "$setup"
    prefix="$RUN_DIR/results/${case_id}-${dialect}-${path}"
    before="$prefix-before.tsv"
    after="$prefix-after.tsv"
    stdout="$prefix.stdout"
    stderr="$prefix.stderr"
    actual_error="$RUN_DIR/normalized-output/${case_id}-${dialect}-${path}.error.tsv"
    : >"$actual_error"
    catalog_snapshot "$dialect" "$before"

    exec_status=0
    if [[ "$path" == direct ]]; then
      run_direct "$dialect" "$sql_path" >"$stdout" 2>"$stderr" || exec_status=$?
    elif [[ "$dialect" == mysql ]]; then
      run_mysql_gateway "$sql_path" >"$stdout" 2>"$stderr" || exec_status=$?
    else
      run_postgres_gateway "$sql_path" >"$stdout" 2>"$stderr" || exec_status=$?
    fi
    catalog_snapshot "$dialect" "$after"

    status=passed
    if [[ "$expected_result" == success ]]; then
      if [[ "$exec_status" -ne 0 ]] || ! cmp -s "$expected_state" "$after"; then
        status=failed
      fi
    else
      if [[ "$exec_status" -eq 0 ]] || \
        ! python3 "$ROOT/normalize.py" --error-dialect "$dialect" "$stderr" "$actual_error" || \
        ! cmp -s "$expected_error" "$actual_error" || ! cmp -s "$expected_state" "$after"; then
        status=failed
      fi
    fi
    if [[ "$unchanged" == yes ]] && ! cmp -s "$before" "$after"; then
      status=failed
    fi

    if [[ "$status" == failed ]]; then
      diff -u "$expected_state" "$after" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.state.diff" || true
      if [[ "$expected_result" == error ]]; then
        diff -u "$expected_error" "$actual_error" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.error.diff" || true
      fi
      if [[ "$unchanged" == yes ]]; then
        diff -u "$before" "$after" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.unchanged.diff" || true
      fi
      fail_count=$((fail_count + 1))
    else
      pass_count=$((pass_count + 1))
    fi
    write_result "$case_id" "$dialect" "$path" "$status" "$expected_result" \
      "$before" "$after" "$actual_error"
  done
done < <(python3 - "$ROOT/manifest.json" "$CASE_FROM" "$CASE_TO" <<'PY'
import json
import sys

manifest, first, last = sys.argv[1:]
for case in json.load(open(manifest, encoding="utf-8"))["cases"]:
    if case.get("family") != "ddl" or not first <= case["id"] <= last:
        continue
    for dialect in case["dialects"]:
        print(case["id"], dialect, case["sql_file"], sep="\t")
PY
)

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json
import sys
from pathlib import Path

results_path, output, case_count, pass_count, fail_count = sys.argv[1:]
results = [json.loads(line) for line in Path(results_path).read_text(encoding="utf-8").splitlines()]
summary = {
    "executions": int(case_count),
    "passed": int(pass_count),
    "failed": int(fail_count),
    "results": results,
}
Path(output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if summary["failed"]:
    raise SystemExit(f"SQLT-3D failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3D passed: {summary['passed']} case/dialect/path executions")
PY

echo "artifacts: $RUN_DIR"
