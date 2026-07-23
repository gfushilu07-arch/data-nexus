#!/usr/bin/env bash
# UI71: verify remainders honesty helper coverage across the smoke matrix.
# Fails if any L0 / security / cedar smoke no longer calls
# assert-security-policies-honesty.py (UI63–66).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXAMPLES="$ROOT/examples"
HELPER="assert-security-policies-honesty.py"

need_helper=(
  # l0
  smoke-admin-auth.sh
  smoke-dual-listener.sh
  smoke-cross-protocol.sh
  smoke-cross-protocol-pg-to-mysql.sh
  smoke-cross-protocol-stream.sh
  # security-core
  smoke-security-deny.sh
  smoke-security-column.sh
  smoke-security-mask.sh
  smoke-security-audit.sh
  smoke-security-audit-sample.sh
  smoke-security-ticket.sh
  smoke-security-portal.sh
  smoke-security-vault.sh
  smoke-security-state-file.sh
  smoke-security-config-validate.sh
  smoke-security-remote-pdp.sh
  # security-extended
  smoke-security-stream.sh
  smoke-security-stream-rss.sh
  smoke-security-passthrough.sh
  smoke-security-watermark.sh
  smoke-security-dual-control.sh
  smoke-security-time.sh
  smoke-security-portal-xproto.sh
  smoke-security-portal-xproto-pg-mysql.sh
  # cedar
  smoke-security-cedar.sh
  smoke-security-cedar-reload.sh
)

missing=0
if [[ ! -f "$EXAMPLES/$HELPER" ]]; then
  echo "FAIL: missing $EXAMPLES/$HELPER" >&2
  exit 1
fi

for s in "${need_helper[@]}"; do
  path="$EXAMPLES/$s"
  if [[ ! -f "$path" ]]; then
    echo "FAIL: missing smoke $s" >&2
    missing=1
    continue
  fi
  if ! grep -q 'assert-security-policies-honesty.py' "$path"; then
    echo "FAIL: $s does not call $HELPER" >&2
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "UI71 honesty helper coverage: FAIL" >&2
  exit 1
fi

echo "UI71 honesty helper coverage: OK (${#need_helper[@]} smokes + $HELPER present)"
