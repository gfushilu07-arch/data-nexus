#!/usr/bin/env bash
# Execute every registered DQL case directly against its declared Docker backend.
# Raw output and machine-readable results stay in the external Data Nexus cache.
set -euo pipefail

export PATH="/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_DQL_RUN_ID:-dql-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
COMPOSE_PROJECT="sqlt3b-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/dql-oracles.json" "$RUN_DIR/dql-oracles.json"
RESULTS="$RUN_DIR/results.jsonl"
: >"$RESULTS"

cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing required command: docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing required command: python3" >&2; exit 1; }
python3 "$ROOT/validate.py"

echo "==> starting fixed-version SQLT Docker backends"
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

run_mysql() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

run_postgres() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

load_fixtures() {
  local dialect="$1"
  if [[ "$dialect" == "mysql" ]]; then
    run_mysql "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/mysql-cleanup.out"
    run_mysql "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/mysql-schema.out"
    run_mysql "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/mysql-seed.out"
  else
    run_postgres "$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/postgres-cleanup.out"
    run_postgres "$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/postgres-schema.out"
    run_postgres "$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/postgres-seed.out"
  fi
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  case_count=$((case_count + 1))
  load_fixtures "$dialect"
  sql_path="$ROOT/cases/$sql_file"
  raw="$RUN_DIR/results/${case_id}-${dialect}.raw"
  err="$RUN_DIR/logs/${case_id}-${dialect}.err"
  normalized="$RUN_DIR/normalized-output/${case_id}-${dialect}.txt"
  expected="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected.txt"
  echo "==> $case_id [$dialect]"
  if [[ "$dialect" == "mysql" ]]; then
    if run_mysql "$sql_path" >"$raw" 2>"$err"; then status=passed; else status=failed; fi
  else
    if run_postgres "$sql_path" >"$raw" 2>"$err"; then status=passed; else status=failed; fi
  fi
  python3 "$ROOT/normalize.py" "$raw" "$normalized"
  python3 - "$ROOT/dql-oracles.json" "$case_id" "$dialect" "$expected" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, destination = sys.argv[1:]
oracles = json.load(open(source, encoding="utf-8"))
Path(destination).write_text(oracles["results"][case_id][dialect], encoding="utf-8")
PY
  if [[ "$status" == passed ]] && ! cmp -s "$expected" "$normalized"; then
    status=mismatch
    diff -u "$expected" "$normalized" >"$RUN_DIR/logs/${case_id}-${dialect}.diff" || true
  fi
  python3 - "$RESULTS" "$case_id" "$dialect" "$sql_file" "$status" "$raw" "$normalized" "$expected" <<'PY'
import json
import sys
from pathlib import Path

results, case_id, dialect, sql_file, status, raw, normalized, expected = sys.argv[1:]
record = {
    "case_id": case_id,
    "dialect": dialect,
    "sql_file": sql_file,
    "status": status,
    "raw_output": str(Path(raw)),
    "normalized_output": str(Path(normalized)),
    "expected_output": str(Path(expected)),
}
with open(results, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True) + "\n")
PY
  if [[ "$status" == passed ]]; then
    pass_count=$((pass_count + 1))
  else
    fail_count=$((fail_count + 1))
    sed -n '1,80p' "$err" >&2 || true
    sed -n '1,120p' "$RUN_DIR/logs/${case_id}-${dialect}.diff" >&2 2>/dev/null || true
  fi
done < <(python3 - "$ROOT/manifest.json" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for case in manifest["cases"]:
    if case["family"] != "dql":
        continue
    for dialect in case["dialects"]:
        print(f'{case["id"]}\t{dialect}\t{case["sql_file"]}')
PY
)

python3 - "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" "$RUN_DIR" <<'PY'
import json
import sys
from pathlib import Path

summary, total, passed, failed, run_dir = sys.argv[1:]
Path(summary).write_text(json.dumps({
    "suite": "SQLT-3B-DQL",
    "total": int(total),
    "passed": int(passed),
    "failed": int(failed),
    "run_dir": run_dir,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "SQLT-3B DQL corpus: $pass_count/$case_count passed"
[[ "$fail_count" == 0 ]]
