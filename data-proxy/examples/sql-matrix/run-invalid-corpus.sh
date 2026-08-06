#!/usr/bin/env bash
# Execute invalid SQL against fixed Docker backends and the security-off gateway.
# Every path verifies stable error identity and exact before/after fixture state.
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
RUN_ID="${SQLT_INVALID_RUN_ID:-invalid-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_INVALID_CASE_FROM:-SQLT-INVALID-001}"
CASE_TO="${SQLT_INVALID_CASE_TO:-SQLT-INVALID-999}"
COMPOSE_PROJECT="sqlt3finvalid-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_LOG="$RUN_DIR/logs/gateway.log"
GATEWAY_PID=""
RESULTS="$RUN_DIR/results.jsonl"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/normalized-output" "$RUN_DIR/results"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/invalid-oracles.json" "$RUN_DIR/invalid-oracles.json"

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
  echo "SQLT-3F1 requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
python3 "$ROOT/validate.py"

echo "==> starting fixed-version SQLT-3F1 Docker backends"
"${COMPOSE[@]}" up -d >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then
    break
  fi
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

run_case() {
  local path="$1"
  local dialect="$2"
  local sql="$3"
  if [[ "$dialect" == mysql && "$path" == direct ]]; then
    run_mysql_direct "$sql"
  elif [[ "$dialect" == mysql ]]; then
    docker run --rm -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
      mysql --batch --raw --skip-column-names --default-character-set=utf8mb4 \
      --ssl-mode=DISABLED -h host.docker.internal -P 29088 -uroot -proot <"$sql"
  elif [[ "$path" == direct ]]; then
    run_postgres_direct "$sql"
  else
    docker run --rm -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
      env PGPASSWORD=root psql -X -q -v ON_ERROR_STOP=1 -v VERBOSITY=verbose \
      -P null=NULL -A -t -F $'\t' -h host.docker.internal -p 29089 -U root -d sqlt <"$sql"
  fi
}

load_fixtures() {
  local dialect="$1"
  local label="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql_direct "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_mysql_direct "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_mysql_direct "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  else
    run_postgres_direct "$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_postgres_direct "$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_postgres_direct "$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  fi
}

oracle_value() {
  python3 - "$ROOT/invalid-oracles.json" "$1" "$2" "$3" <<'PY'
import json
import sys
source, case_id, dialect, field = sys.argv[1:]
data = json.load(open(source, encoding="utf-8"))
if field == "probe_query":
    print(data["probe_queries"][dialect])
elif field == "probe_state":
    sys.stdout.write(data["probe_state"][dialect])
else:
    sys.stdout.write(data["results"][case_id][dialect][field])
PY
}

total=0
passed=0
failed=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  for path in direct gateway; do
    total=$((total + 1))
    label="${case_id}-${dialect}-${path}"
    echo "==> $case_id [$dialect/$path]"
    load_fixtures "$dialect" "$label"
    sql="$ROOT/cases/$sql_file"
    probe_relative="$(oracle_value "$case_id" "$dialect" probe_query)"
    probe="$ROOT/$probe_relative"
    before="$RUN_DIR/results/${label}.before.tsv"
    after="$RUN_DIR/results/${label}.after.tsv"
    stdout="$RUN_DIR/results/${label}.stdout"
    stderr="$RUN_DIR/results/${label}.stderr"
    normalized_error="$RUN_DIR/normalized-output/${label}.error.tsv"
    expected_error="$RUN_DIR/normalized-output/${label}.expected-error.tsv"
    expected_state="$RUN_DIR/normalized-output/${label}.expected-state.tsv"
    if [[ "$dialect" == mysql ]]; then
      run_mysql_direct "$probe" >"$before"
    else
      run_postgres_direct "$probe" >"$before"
    fi
    if run_case "$path" "$dialect" "$sql" >"$stdout" 2>"$stderr"; then
      execution="unexpected_success"
    else
      execution="backend_error"
    fi
    if [[ "$dialect" == mysql ]]; then
      run_mysql_direct "$probe" >"$after"
    else
      run_postgres_direct "$probe" >"$after"
    fi
    python3 "$ROOT/normalize.py" --error-dialect "$dialect" "$stderr" "$normalized_error"
    oracle_value "$case_id" "$dialect" error >"$expected_error"
    oracle_value "$case_id" "$dialect" probe_state >"$expected_state"
    status=passed
    if [[ "$execution" != backend_error ]] || ! cmp -s "$expected_error" "$normalized_error" \
      || ! cmp -s "$expected_state" "$before" || ! cmp -s "$before" "$after"; then
      status=failed
      diff -u "$expected_error" "$normalized_error" >"$RUN_DIR/logs/${label}-error.diff" || true
      diff -u "$expected_state" "$before" >"$RUN_DIR/logs/${label}-before.diff" || true
      diff -u "$before" "$after" >"$RUN_DIR/logs/${label}-state.diff" || true
    fi
    python3 - "$RESULTS" "$case_id" "$dialect" "$path" "$sql_file" "$status" "$execution" "$normalized_error" "$before" "$after" <<'PY'
import json
import sys
from pathlib import Path
results, case_id, dialect, path, sql_file, status, execution, error, before, after = sys.argv[1:]
with Path(results).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id, "dialect": dialect, "path": path, "sql_file": sql_file,
        "status": status, "class": execution, "error": error,
        "before_state": before, "after_state": after,
    }, sort_keys=True) + "\n")
PY
    if [[ "$status" == passed ]]; then
      passed=$((passed + 1))
    else
      failed=$((failed + 1))
      sed -n '1,40p' "$stderr" >&2 || true
      sed -n '1,80p' "$RUN_DIR/logs/${label}-error.diff" >&2 || true
      sed -n '1,80p' "$RUN_DIR/logs/${label}-state.diff" >&2 || true
    fi
  done
done < <(python3 "$ROOT/select_invalid_cases.py" "$ROOT/manifest.json" "$ROOT/invalid-oracles.json" "$CASE_FROM" "$CASE_TO")

python3 - "$RUN_DIR/summary.json" "$total" "$passed" "$failed" "$RUN_DIR" <<'PY'
import json
import sys
from pathlib import Path
summary, total, passed, failed, run_dir = sys.argv[1:]
Path(summary).write_text(json.dumps({
    "suite": "SQLT-3F1", "path_executions": int(total), "passed": int(passed),
    "failed": int(failed), "run_dir": run_dir,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "SQLT-3F1 invalid corpus: $passed/$total path executions passed"
echo "artifacts: $RUN_DIR"
[[ "$total" -gt 0 && "$failed" == 0 ]]
