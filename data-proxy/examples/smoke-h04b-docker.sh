#!/usr/bin/env bash
# H04b: local Docker HTTPS + Keycloak OIDC/JWKS + role mapping acceptance.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE="$ROOT/examples/h04b"
CACHE="${DATA_NEXUS_H04B_CACHE_DIR:-/Volumes/fushilu/.caches/data-nexus/h04b}"
COMPOSE=(docker compose -f "$FIXTURE/docker-compose.yml")
CA="$CACHE/certs/ca.crt"
REPORT="$CACHE/report.txt"
KEEP_STACK=false
CERT_SAN='DNS:ui.localhost,DNS:idp.localhost,DNS:gateway.localhost,DNS:gateway-wrong-issuer.localhost'

if [[ "${1:-}" == "--keep" ]]; then
  KEEP_STACK=true
fi

export H04B_CACHE_DIR="$CACHE"

cleanup() {
  "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1 || true
}
cleanup_before_start() {
  cleanup
}
trap 'if [[ "$KEEP_STACK" != true ]]; then cleanup; fi' EXIT

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }; }
need curl; need docker; need openssl; need python3

mkdir -p "$CACHE/certs" "$CACHE/ui-work" \
  "$CACHE/keycloak-tmp" \
  "$CACHE/pnpm-store" "$CACHE/cargo-home/registry" "$CACHE/cargo-home/git" \
  "$CACHE/cargo-target-linux"
rm -rf "$CACHE/keycloak-data"
mkdir -p "$CACHE/keycloak-data/import"
cp "$FIXTURE/realm.json" "$CACHE/keycloak-data/import/data-nexus-realm.json"
: >"$REPORT"

if [[ ! -s "$CACHE/certs/server.crt" || ! -s "$CACHE/certs/server.key" ]] || \
  ! openssl x509 -in "$CACHE/certs/server.crt" -noout -ext subjectAltName 2>/dev/null | \
    grep -q 'DNS:gateway-wrong-issuer.localhost'; then
  echo "==> generating local CA and HTTPS certificate"
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
    -subj '/CN=Data Nexus H04b Local CA' \
    -keyout "$CACHE/certs/ca.key" -out "$CA" >/dev/null 2>&1
  openssl req -newkey rsa:2048 -nodes -subj '/CN=ui.localhost' \
    -keyout "$CACHE/certs/server.key" -out "$CACHE/certs/server.csr" >/dev/null 2>&1
  printf '%s\n' "subjectAltName=$CERT_SAN" \
    'extendedKeyUsage=serverAuth' >"$CACHE/certs/server.ext"
  openssl x509 -req -days 30 -sha256 -in "$CACHE/certs/server.csr" \
    -CA "$CA" -CAkey "$CACHE/certs/ca.key" -CAcreateserial \
    -extfile "$CACHE/certs/server.ext" -out "$CACHE/certs/server.crt" >/dev/null 2>&1
fi

echo "==> building Linux Rust gateway into external cache"
if [[ "${H04B_SKIP_GATEWAY_BUILD:-false}" == true ]]; then
  [[ -x "$CACHE/cargo-target-linux/debug/proxy" ]] || {
    echo "H04B_SKIP_GATEWAY_BUILD=true but cached Linux proxy is missing" >&2
    exit 1
  }
  echo "using cached Linux gateway: $CACHE/cargo-target-linux/debug/proxy"
else
  docker build -q -t data-nexus-h04b-builder:1.94 -f "$FIXTURE/Dockerfile.builder" "$FIXTURE" >/dev/null
  docker run --rm -v "$ROOT:/workspace:ro" \
    -v "$CACHE/cargo-home/registry:/usr/local/cargo/registry" \
    -v "$CACHE/cargo-home/git:/usr/local/cargo/git" \
    -v "$CACHE/cargo-target-linux:/target" -w /workspace -e CARGO_TARGET_DIR=/target \
    data-nexus-h04b-builder:1.94 \
    cargo build --locked -p data-proxy --bin proxy
fi

echo "==> generating OIDC-enabled data-ui into external cache"
UI_ROOT="$(cd "$ROOT/../data-ui" && pwd)"
if [[ "${H04B_SKIP_UI_BUILD:-false}" == true ]]; then
  [[ -s "$CACHE/ui-work/.output/public/index.html" ]] || {
    echo "H04B_SKIP_UI_BUILD=true but cached data-ui output is missing" >&2
    exit 1
  }
  echo "using cached data-ui: $CACHE/ui-work/.output/public"
else
  docker run --rm -v "$UI_ROOT:/source:ro" -v "$CACHE/ui-work:/app" \
    -v "$CACHE/pnpm-store:/pnpm/store" -w /app -e CI=true -e PNPM_HOME=/pnpm \
    -e PNPM_STORE_DIR=/pnpm/store \
    -e NUXT_PUBLIC_ADMIN_API_BASE=https://gateway.localhost:8443 \
    -e NUXT_PUBLIC_OIDC_ISSUER=https://idp.localhost:8443/realms/data-nexus \
    -e NUXT_PUBLIC_OIDC_CLIENT_ID=data-nexus-admin \
    -e NUXT_PUBLIC_OIDC_REDIRECT_URI=https://ui.localhost:8443/auth/callback \
    -e NUXT_PUBLIC_OIDC_SCOPES='openid profile email' \
    node:22-alpine sh -eu -c '
      find /app -mindepth 1 -maxdepth 1 \
        ! -name .nuxt ! -name .output ! -name node_modules ! -name .pnpm-store \
        -exec rm -rf {} +
      tar -C /source --exclude=node_modules --exclude=.nuxt --exclude=.output --exclude=dist -cf - . \
        | tar -C /app -xf -
      corepack enable
      corepack pnpm@10.31.0 install --frozen-lockfile
      corepack pnpm@10.31.0 generate
    '
fi

echo "==> starting Keycloak, gateway, UI, and HTTPS edge"
cleanup_before_start
"${COMPOSE[@]}" up -d

wait_url() {
  local label="$1" url="$2"
  for _ in $(seq 1 180); do
    if curl --cacert "$CA" -fsS "$url" >/dev/null 2>&1; then echo "$label ready"; return 0; fi
    sleep 1
  done
  "${COMPOSE[@]}" logs --tail=120 >&2
  return 1
}

wait_url keycloak 'https://idp.localhost:8443/realms/data-nexus/.well-known/openid-configuration'
wait_url gateway 'https://gateway.localhost:8443/healthz'
wait_url wrong-issuer-gateway 'https://gateway-wrong-issuer.localhost:8443/healthz'
wait_url data-ui 'https://ui.localhost:8443/login'

TOKEN_URL='https://idp.localhost:8443/realms/data-nexus/protocol/openid-connect/token'
DISCOVERY_URL='https://idp.localhost:8443/realms/data-nexus/.well-known/openid-configuration'
API='https://gateway.localhost:8443'
WRONG_ISSUER_API='https://gateway-wrong-issuer.localhost:8443'

token_for() {
  curl --cacert "$CA" --fail-with-body -sS -X POST "$TOKEN_URL" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode grant_type=password --data-urlencode client_id=data-nexus-admin \
    --data-urlencode username="$1" --data-urlencode password="$2" \
    --data-urlencode scope='openid profile email'
}

assert_me() {
  local user="$1" password="$2" expected="$3"
  local json token
  json="$(token_for "$user" "$password")" || return 1
  token="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$json")" || return 1
  curl --cacert "$CA" --fail-with-body -sS "$API/admin/me" \
    -H "Authorization: Bearer $token" >"$CACHE/$user-me.json" || return 1
  python3 - "$user" "$expected" "$CACHE/$user-me.json" <<'PY'
import json, sys
user, expected, path = sys.argv[1:]
me = json.load(open(path))
assert expected in me["roles"], (user, me)
assert me["auth_method"] == "jwt_jwks", me
assert me["subject"], (user, me)
print(user, "->", me["roles"], me["auth_method"], file=sys.stderr)
PY
  [[ "$?" == 0 ]] || return 1
  printf '%s\n' "$token"
}

echo '==> HTTPS and OIDC discovery'
curl --cacert "$CA" -fsS "$DISCOVERY_URL" >"$CACHE/discovery.json"
printf 'https and discovery: OK\n' >>"$REPORT"

echo '==> no token -> 401'
code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' "$API/admin/listeners")"
[[ "$code" == 401 ]] || { echo "expected 401, got $code"; exit 1; }
printf 'no token: 401\n' >>"$REPORT"

echo '==> viewer/operator/admin role mapping and permission boundaries'
VIEWER="$(assert_me viewer-user viewer-password viewer)"
OPERATOR="$(assert_me operator-user operator-password operator)"
ADMIN="$(assert_me admin-user admin-password admin)"
for token in "$VIEWER" "$OPERATOR"; do
  code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' -X POST "$API/admin/reload" -H "Authorization: Bearer $token")"
  [[ "$code" == 403 ]] || { echo "expected protected reload 403, got $code"; exit 1; }
done
code="$(curl --cacert "$CA" -sS -o "$CACHE/admin-reload.json" -w '%{http_code}' -X POST "$API/admin/reload" -H "Authorization: Bearer $ADMIN")"
[[ "$code" == 200 ]] || { echo "expected admin reload 200, got $code"; exit 1; }
printf 'role mapping and permissions: OK\n' >>"$REPORT"

echo '==> wrong audience and unmapped role -> 401/403'
BAD_AUD="$(curl --cacert "$CA" -fsS -X POST "$TOKEN_URL" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=password --data-urlencode client_id=wrong-audience \
  --data-urlencode username=viewer-user --data-urlencode password=viewer-password | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' "$API/admin/me" -H "Authorization: Bearer $BAD_AUD")"
[[ "$code" == 401 ]] || { echo "expected wrong audience 401, got $code"; exit 1; }
UNKNOWN_TOKEN="$(token_for unknown-user unknown-password | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' -X POST "$API/admin/reload" -H "Authorization: Bearer $UNKNOWN_TOKEN")"
[[ "$code" == 403 ]] || { echo "expected unmapped role 403, got $code"; exit 1; }
NO_ROLE_TOKEN="$(token_for no-role-user no-role-password | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' -X POST "$API/admin/reload" -H "Authorization: Bearer $NO_ROLE_TOKEN")"
[[ "$code" == 403 ]] || { echo "expected missing role 403, got $code"; exit 1; }
printf 'audience, unmapped role, and missing role rejection: OK\n' >>"$REPORT"

echo '==> issuer mismatch -> 401'
code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' "$WRONG_ISSUER_API/admin/me" -H "Authorization: Bearer $VIEWER")"
[[ "$code" == 401 ]] || { echo "expected issuer mismatch 401, got $code"; exit 1; }
printf 'issuer mismatch rejection: OK\n' >>"$REPORT"

echo '==> expired token -> 401'
EXPIRED_TOKEN="$(curl --cacert "$CA" --fail-with-body -sS -X POST "$TOKEN_URL" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=password --data-urlencode client_id=short-lived \
  --data-urlencode username=viewer-user --data-urlencode password=viewer-password | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
sleep 3
code="$(curl --cacert "$CA" -sS -o /dev/null -w '%{http_code}' "$API/admin/me" -H "Authorization: Bearer $EXPIRED_TOKEN")"
[[ "$code" == 401 ]] || { echo "expected expired token 401, got $code"; exit 1; }
printf 'expired token rejection: OK\n' >>"$REPORT"

echo '==> local browser PKCE callback'
printf 'browser PKCE callback: run the Playwright CLI against https://ui.localhost:8443/login\n' >>"$REPORT"
cat "$REPORT"
if [[ "$KEEP_STACK" == true ]]; then
  echo "stack is running for Playwright; stop it with: ${COMPOSE[*]} down"
else
  echo "API/JWKS/role smoke passed; browser PKCE is a separate Playwright step"
fi
