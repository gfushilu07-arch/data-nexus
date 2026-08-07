#!/usr/bin/env bash
# Execute SQLT-3F3 dangerous capability and cross-dialect boundaries in Docker.
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
RUN_ID="${SQLT_UNSUPPORTED_RUN_ID:-unsupported-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
COMPOSE_PROJECT="sqlt3funsupported-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml" \
  -f "$ROOT/fixtures/docker-compose-unsupported.yml")
CLIENT_IMAGE="${SQLT_UNSUPPORTED_CLIENT_IMAGE:-sqlt-unsupported-client:3f3}"
CALIBRATE="${SQLT_UNSUPPORTED_CALIBRATE:-0}"
CASE_FROM="${SQLT_UNSUPPORTED_CASE_FROM:-SQLT-UNSUPPORTED-001}"
CASE_TO="${SQLT_UNSUPPORTED_CASE_TO:-SQLT-UNSUPPORTED-009}"
RESULTS="$RUN_DIR/results.jsonl"
SELECTION="$RUN_DIR/selection.tsv"
GATEWAY_PID=""

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output" "$RUN_DIR/preflight"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/unsupported-oracles.json" "$RUN_DIR/unsupported-oracles.json"

cleanup() {
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

stop_gateway() {
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID"
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  GATEWAY_PID=""
}

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing curl" >&2; exit 1; }
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-3F3 requires rustc 1.94.1; found: $(rustc --version)" >&2
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
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt_admin -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then
    break
  fi
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent
"${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt_admin -d sqlt

run_mysql_admin() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt "$@"
}

run_postgres_bootstrap() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -P null=NULL -A -t -F $'\t' -U sqlt_admin -d sqlt "$@"
}

run_postgres_admin() {
  PGPASSWORD=sqlt-admin-password "${COMPOSE[@]}" exec -T -e PGPASSWORD=sqlt-admin-password postgres \
    psql -X -q -v ON_ERROR_STOP=1 -P null=NULL -A -t -F $'\t' \
    -h 127.0.0.1 -U sqlt_admin -d sqlt "$@"
}

# The Compose override initializes sqlt_admin as the bootstrap owner. Create a
# separate restricted login for every dangerous direct and gateway backend path.
run_postgres_bootstrap -c "CREATE ROLE sqlt LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOREPLICATION NOBYPASSRLS PASSWORD 'sqlt';" \
  >"$RUN_DIR/preflight/postgres-restricted-role-create.tsv"
run_postgres_admin -c "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname IN ('sqlt', 'sqlt_admin') ORDER BY rolname;" \
  >"$RUN_DIR/preflight/postgres-role-transition.tsv"

run_mysql_admin -e "SHOW GRANTS FOR 'sqlt'@'%';" >"$RUN_DIR/preflight/mysql-grants.tsv"
run_mysql_admin -e "SELECT COUNT(*) FROM information_schema.USER_PRIVILEGES WHERE GRANTEE = '''sqlt''@''%''' AND PRIVILEGE_TYPE IN ('FILE','SUPER','SYSTEM_VARIABLES_ADMIN','PERSIST_RO_VARIABLES_ADMIN');" \
  >"$RUN_DIR/preflight/mysql-dangerous-privileges.tsv"
run_postgres_admin -c "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname = 'sqlt';" \
  >"$RUN_DIR/preflight/postgres-dangerous-privileges.tsv"
[[ "$(tr -d '[:space:]' <"$RUN_DIR/preflight/mysql-dangerous-privileges.tsv")" == 0 ]] || {
  echo "mysql sqlt unexpectedly has a dangerous privilege" >&2; exit 1;
}
[[ "$(tr -d '[:space:]' <"$RUN_DIR/preflight/postgres-dangerous-privileges.tsv")" == ffff ]] || {
  echo "postgres sqlt unexpectedly has a dangerous role attribute" >&2; exit 1;
}

GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == 1 || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && cargo build -p data-proxy --bin proxy) >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" >"$RUN_DIR/logs/cargo-build.log"
fi
RUST_LOG="${SQLT_UNSUPPORTED_RUST_LOG:-warn,data_nexus::audit=info}" \
  DATA_NEXUS_LOG_FORMAT=json \
  "$GATEWAY_BIN" daemon -c "$ROOT/fixtures/gateway-config.toml" \
  >"$RUN_DIR/logs/gateway.log" 2>&1 &
GATEWAY_PID=$!
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null; then
    break
  fi
  kill -0 "$GATEWAY_PID" 2>/dev/null || { echo "gateway exited early" >&2; exit 1; }
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

load_fixture() {
  local dialect="$1" label="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql_admin <"$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_mysql_admin <"$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_mysql_admin <"$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  else
    run_postgres_admin <"$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_postgres_admin <"$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_postgres_admin <"$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
    run_postgres_admin -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sqlt;" \
      >"$RUN_DIR/logs/${label}-grant.out"
  fi
}

probe_state() {
  local dialect="$1" output="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql_admin <"$ROOT/fixtures/mysql/oracle-unsupported-state.sql" >"$output"
  else
    run_postgres_admin <"$ROOT/fixtures/postgres/oracle-unsupported-state.sql" >"$output"
  fi
}

run_client() {
  local case_id="$1" dialect="$2" path="$3" sql_file="$4" output="$5"
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
    python /matrix/unsupported_client.py --case-id "$case_id" --dialect "$dialect" --path "$path" \
    --sql "/matrix/cases/$sql_file" --host host.docker.internal --port "$port" \
    --user "$user" --password "$password" >"$output"
}

expected_semantic() {
  python3 - "$ROOT/unsupported-oracles.json" "$1" "$2" "$3" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))["results"][sys.argv[2]]["expected"][sys.argv[3]][sys.argv[4]]
print(json.dumps(value, sort_keys=True, separators=(",", ":")))
PY
}

total=0
passed=0
failed=0
python3 "$ROOT/select_unsupported_cases.py" "$ROOT/manifest.json" "$ROOT/unsupported-oracles.json" \
  | awk -F '\t' -v first="$CASE_FROM" -v last="$CASE_TO" '$1 >= first && $1 <= last' >"$SELECTION"
selected="$(wc -l <"$SELECTION" | tr -d '[:space:]')"
[[ "$selected" -gt 0 ]] || { echo "no unsupported cases selected" >&2; exit 1; }

exec 3<"$SELECTION"
while IFS=$'\t' read -r case_id dialect sql_file flow <&3; do
  [[ -n "$case_id" ]] || continue
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
    if ! run_client "$case_id" "$dialect" "$path" "$sql_file" "$output" \
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
    if [[ -s "$semantic" ]]; then
      if ! python3 - "$semantic" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
assert value["connection"] == "same"
assert value["recovery_rows"] == [["42"]]
assert value["session_before"] == value["session_after"]
assert value["steps"]
PY
      then
        status=failed
      fi
    fi
    if [[ "$CALIBRATE" != 1 && -s "$semantic" ]]; then
      expected_semantic "$case_id" "$dialect" "$path" >"$expected"
      actual_steps="$RUN_DIR/normalized-output/${label}.steps.json"
      python3 - "$semantic" "$actual_steps" <<'PY'
import json, sys
from pathlib import Path
value = json.load(open(sys.argv[1], encoding="utf-8"))["steps"]
Path(sys.argv[2]).write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
      if ! cmp -s "$expected" "$actual_steps"; then
        status=failed
        diff -u "$expected" "$actual_steps" >"$RUN_DIR/logs/${label}-semantic.diff" || true
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
done
exec 3<&-

expected_paths=$((selected * 2))
if [[ "$total" != "$expected_paths" ]]; then
  echo "unsupported path count mismatch: selected=$selected expected=$expected_paths actual=$total" >&2
  exit 1
fi

# Stop the process before inspecting its JSON log so all audit output is flushed.
stop_gateway
python3 "$ROOT/verify_unsupported_audit.py" \
  "$RESULTS" "$RUN_DIR/logs/gateway.log" "$RUN_DIR/audit-summary.json"

python3 - "$RUN_DIR/summary.json" "$total" "$passed" "$failed" "$RUN_DIR" "$CALIBRATE" <<'PY'
import json, sys
from pathlib import Path
summary, total, passed, failed, run_dir, calibrate = sys.argv[1:]
Path(summary).write_text(json.dumps({"suite": "SQLT-3F3", "path_executions": int(total),
    "passed": int(passed), "failed": int(failed), "calibration": calibrate == "1", "run_dir": run_dir},
    indent=2) + "\n", encoding="utf-8")
PY

echo "SQLT-3F3 unsupported corpus: $passed/$total path executions passed"
echo "artifacts: $RUN_DIR"
[[ "$total" == "$expected_paths" && "$failed" == 0 ]]
