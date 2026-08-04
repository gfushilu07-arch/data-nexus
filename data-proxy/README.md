# Data Nexus Rust Workspace

本目录是 Data Nexus 当前产品的 Rust workspace，不是独立于 Data Nexus 的另一个项目。
目录名 `data-proxy` 来自早期代码布局，产品名称与根看板统一使用 **Data Nexus**。

主要能力包括 MySQL/PostgreSQL 协议网关、路由与连接池、安全策略、结果义务、
审计、Admin API、Portal API 和可选 OpenTelemetry/Cedar/OpenDAL 集成。

## 构建

Rust 版本由 [`rust-toolchain.toml`](rust-toolchain.toml) 固定，Cargo 产物必须写入
`/Volumes/fushilu/.caches/data-nexus/cargo-target`。

```shell
CARGO_TARGET_DIR=/Volumes/fushilu/.caches/data-nexus/cargo-target \
  cargo build --package data-proxy --bin proxy
CARGO_TARGET_DIR=/Volumes/fushilu/.caches/data-nexus/cargo-target \
  cargo test --workspace
```

未完成任务以根目录 [`todo.md`](../todo.md) 为准，已交付记录见
[`todo-impl.md`](../todo-impl.md)。开发规则见
[`data-nexus-development.md`](../.claude/rules/data-nexus-development.md)。
