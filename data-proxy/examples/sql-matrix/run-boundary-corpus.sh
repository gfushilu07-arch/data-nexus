#!/usr/bin/env bash
# Execute SQLT-3F2 protocol, lexical, and fixed resource boundaries in Docker.
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
RUN_ID="${SQLT_BOUNDARY_RUN_ID:-boundary-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
COMPOSE_PROJECT="sqlt3fboundary-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
CLIENT_IMAGE="${SQLT_BOUNDARY_CLIENT_IMAGE:-sqlt-boundary-client:3f2}"
CALIBRATE="${SQLT_BOUNDARY_CALIBRATE:-0}"
CASE_FROM="${SQLT_BOUNDARY_CASE_FROM:-SQLT-INVALID-014}"
CASE_TO="${SQLT_BOUNDARY_CASE_TO:-SQLT-INVALID-021}"
RESULTS="$RUN_DIR/results.jsonl"
GATEWAY_PID=""

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/boundary-oracles.json" "$RUN_DIR/boundary-oracles.json"

cleanup() {
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing curl" >&2; exit 1; }
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-3F2 requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
if [[ "$CALIBRATE" != 1 ]]; then
  python3 "$ROOT/validate.py"
fi

if ! docker image inspect "$CLIENT_IMAGE" >/dev/null 2>&1; then
  docker build --pull=false -t "$CLIENT_IMAGE" -f - . >"$RUN_DIR/logs/client-image-build.log" 2>&1 <<'DOCKERFILE'
FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir --disable-pip-version-check "mysql-connector-python==9.4.0"
DOCKERFILE
else
  echo "reusing client image: $CLIENT_IMAGE" >"$RUN_DIR/logs/client-image-build.log"
fi

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

GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == 1 || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && cargo build -p data-proxy --bin proxy) >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" >"$RUN_DIR/logs/cargo-build.log"
fi
"$GATEWAY_BIN" daemon -c "$ROOT/fixtures/gateway-config.toml" >"$RUN_DIR/logs/gateway.log" 2>&1 &
GATEWAY_PID=$!
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null; then
    break
  fi
  kill -0 "$GATEWAY_PID" 2>/dev/null || { echo "gateway exited early" >&2; exit 1; }
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

run_mysql_root() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

run_postgres_root() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

load_fixture() {
  local dialect="$1" label="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql_root "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_mysql_root "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_mysql_root "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  else
    run_postgres_root "$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_postgres_root "$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_postgres_root "$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  fi
}

probe_state() {
  local dialect="$1" output="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql_root "$ROOT/fixtures/mysql/oracle-invalid-state.sql" >"$output"
  else
    run_postgres_root "$ROOT/fixtures/postgres/oracle-invalid-state.sql" >"$output"
  fi
}

run_client() {
  local case_id="$1" dialect="$2" path="$3" sql_file="$4" flow="$5" output="$6"
  local port user password
  if [[ "$dialect" == mysql ]]; then
    port=23306; user=sqlt; password=sqlt
    [[ "$path" == gateway ]] && { port=29088; user=root; password=root; }
  else
    port=25432; user=sqlt; password=sqlt
    [[ "$path" == gateway ]] && { port=29089; user=root; password=root; }
  fi
  docker run --rm --add-host=host.docker.internal:host-gateway \
    -v "$ROOT:/matrix:ro" "$CLIENT_IMAGE" \
    python /matrix/boundary_client.py --case-id "$case_id" --dialect "$dialect" --path "$path" \
    --flow "$flow" --sql "/matrix/cases/$sql_file" --host host.docker.internal --port "$port" \
    --user "$user" --password "$password" >"$output"
}

expected_semantic() {
  python3 - "$ROOT/boundary-oracles.json" "$1" "$2" "$3" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))["results"][sys.argv[2]]["expected"][sys.argv[3]][sys.argv[4]]
print(json.dumps(value, sort_keys=True, separators=(",", ":")))
PY
}

total=0
passed=0
failed=0
while IFS=$'\t' read -r case_id dialect sql_file flow; do
  [[ -n "$case_id" ]] || continue
  [[ "$case_id" < "$CASE_FROM" || "$case_id" > "$CASE_TO" ]] && continue
  for path in direct gateway; do
    total=$((total + 1))
    label="${case_id}-${dialect}-${path}"
    echo "==> $case_id [$dialect/$path/$flow]"
    load_fixture "$dialect" "$label"
    before="$RUN_DIR/results/${label}.before.tsv"
    after="$RUN_DIR/results/${label}.after.tsv"
    output="$RUN_DIR/results/${label}.json"
    semantic="$RUN_DIR/normalized-output/${label}.semantic.json"
    expected="$RUN_DIR/normalized-output/${label}.expected.json"
    probe_state "$dialect" "$before"
    status=passed
    if ! run_client "$case_id" "$dialect" "$path" "$sql_file" "$flow" "$output" \
      2>"$RUN_DIR/results/${label}.stderr"; then
      status=failed
    fi
    probe_state "$dialect" "$after"
    if [[ -s "$output" ]]; then
      python3 - "$output" "$semantic" <<'PY'
import json, sys
from pathlib import Path
value = json.load(open(sys.argv[1], encoding="utf-8"))["semantic"]
Path(sys.argv[2]).write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
    else
      status=failed
    fi
    if ! cmp -s "$before" "$after"; then
      status=failed
      diff -u "$before" "$after" >"$RUN_DIR/logs/${label}-state.diff" || true
    fi
    if [[ "$CALIBRATE" != 1 && -s "$semantic" ]]; then
      expected_semantic "$case_id" "$dialect" "$path" >"$expected"
      if ! cmp -s "$expected" "$semantic"; then
        status=failed
        diff -u "$expected" "$semantic" >"$RUN_DIR/logs/${label}-semantic.diff" || true
      fi
    fi
    python3 - "$RESULTS" "$case_id" "$dialect" "$path" "$flow" "$sql_file" "$status" "$semantic" "$before" "$after" <<'PY'
import json, sys
from pathlib import Path
results, case_id, dialect, path, flow, sql_file, status, semantic, before, after = sys.argv[1:]
value = json.load(open(semantic, encoding="utf-8")) if Path(semantic).is_file() else None
with open(results, "a", encoding="utf-8") as out:
    out.write(json.dumps({"case_id": case_id, "dialect": dialect, "path": path, "flow": flow,
                          "sql_file": sql_file, "status": status, "semantic": value,
                          "before_state": before, "after_state": after}, sort_keys=True) + "\n")
PY
    if [[ "$status" == passed ]]; then
      passed=$((passed + 1))
    else
      failed=$((failed + 1))
      sed -n '1,60p' "$RUN_DIR/results/${label}.stderr" >&2 || true
      sed -n '1,100p' "$RUN_DIR/logs/${label}-semantic.diff" >&2 || true
      sed -n '1,100p' "$RUN_DIR/logs/${label}-state.diff" >&2 || true
    fi
  done
done < <(python3 "$ROOT/select_boundary_cases.py" "$ROOT/manifest.json" "$ROOT/boundary-oracles.json")

python3 - "$RUN_DIR/summary.json" "$total" "$passed" "$failed" "$RUN_DIR" "$CALIBRATE" <<'PY'
import json, sys
from pathlib import Path
summary, total, passed, failed, run_dir, calibrate = sys.argv[1:]
Path(summary).write_text(json.dumps({"suite": "SQLT-3F2", "path_executions": int(total),
    "passed": int(passed), "failed": int(failed), "calibration": calibrate == "1", "run_dir": run_dir},
    indent=2) + "\n", encoding="utf-8")
PY

echo "SQLT-3F2 boundary corpus: $passed/$total path executions passed"
echo "artifacts: $RUN_DIR"
[[ "$total" -gt 0 && "$failed" == 0 ]]
