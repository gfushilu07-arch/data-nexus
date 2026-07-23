---
paths: data-proxy/examples/**, **/*smoke*, **/*test*, **/*Test*, .github/workflows/**, data-proxy/**/Cargo.toml, data-proxy/rust-toolchain.toml, data-proxy/docs/build-cache.md
---

# 测试与 Smoke（强制补充）

## 工具链

- rustc：**1.94.1**（`data-proxy/rust-toolchain.toml`）
- `CARGO_TARGET_DIR`：外置，见 `data-proxy/docs/build-cache.md`
- 禁止在仓库内写多 GB `.cargo-target*`

```bash
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN=1.94.1
export PATH="/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin:$PATH"
```

## Smoke 组

| 组 | 内容 | 何时跑 |
|----|------|--------|
| `l0` | security off | 协议/路由改动 |
| `security-core` | deny/column/mask/audit/**audit-sample**/ticket/portal/vault/**state-file**/`config-validate`/**remote-pdp** | **安全默认门禁** |
| `default` | l0 + security-core | **PR / commit 默认** |
| `security-extended` | stream/**stream-rss**/passthrough/watermark/dual-control/time/xproto/**portal-xproto×2** | 流式/透传/时间窗/跨协议 portal |
| `cedar` | cedar + reload | 需 `--features security-cedar` |
| `all` | default + extended | 发版前 |

```bash
cd data-proxy
./examples/run-smoke-matrix.sh default
# cedar 需先：
cargo build -p data-proxy --bin proxy --features security-cedar
./examples/run-smoke-matrix.sh cedar
# 发版后恢复默认二进制（无 optional feature）
cargo build -p data-proxy --bin proxy
```

## Remainders honesty pins (UI52–71)

Security smokes and L0 dual/xproto/admin-auth assert `GET /admin/security-policies`:

| Field | Value | Meaning |
|-------|-------|---------|
| `remainders.backend_sql_with_hold` | `false` | A10 not backend SQL WITH HOLD |
| `remainders.crdt_merge` | `false` | H05 not CRDT |
| `remainders.mlock` | `false` | H05 not mlock |
| `remainders.process_rss_window_byte_ci` | `false` | A06 not exact 1–2 window process RSS CI |

Also pin `sql_cursor.process_local=true` / `backend_with_hold=false` and
`streaming.peak_is_process_rss=false` / `obligations_force_streaming=true`.
Do not drop these asserts when editing smokes.

Shared helper (UI63): `examples/assert-security-policies-honesty.py`
(`--file` / `--url` / `--bearer` / `--expect-enabled`). Prefer it for L0/auth smokes (dual-listener, cross-protocol×3, admin-auth; UI63/UI64)
security-core (UI65) and security-extended/cedar (UI66: stream/rss/passthrough/watermark/
dual-control/time/portal-xproto/cedar).
Inline asserts may remain for extra field checks; helper is the remainders contract.

Coverage gate (UI71): `examples/check-honesty-helper-coverage.sh` fails if any matrix
smoke drops the helper call.

## 纪律

1. Smoke 启动前 **pkill** 残留 `/debug/proxy`。
2. DB seed 防 schema 漂移：必要时 **DROP+CREATE**。
3. `security.enabled=false` 行为不得被安全改动破坏。
4. Feature 任务在对应 feature 下测。
5. 单测优先 `gateway_core` / `runtime_gateway` 相关 lib filter，再 smoke。

## CI（H07）

- Workflow：`.github/workflows/smoke-matrix.yml`
- **rustc 钉 1.94.1**（`dtolnay/rust-toolchain@1.94.1`，与 `rust-toolchain.toml` 一致）
- **PR / push**（`data-proxy/**`）：job `smoke-default` → `./examples/run-smoke-matrix.sh default`
- **schedule**（每日 UTC 03:17）：`smoke-extended` + `smoke-cedar`（不重复 default）
- **workflow_dispatch** `group`：
  - `default` / `l0` / `security-core` → default job
  - `security-extended` / `all` → extended job（`all` 时 default 与 extended 都跑）
  - `cedar` → cedar job（预编译 `--features security-cedar`）
- Cedar **不进** PR 门禁（可选 feature；发版前本地或 dispatch `cedar`）

实现或修测时用 skill **dn-smoke** 或 `/dn-smoke`；提交前用 **dn-dod** / `/dn-dod`。
