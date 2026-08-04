# Data Nexus

Data Nexus 是一个使用 Rust 开发的数据库协议网关。当前产品实现位于
[`data-proxy/`](data-proxy/) Cargo workspace，提供 MySQL/PostgreSQL 协议接入、
连接池与路由、安全策略、审计、管理 API 和可选管理界面。

## 项目入口

| 路径 | 用途 |
|------|------|
| `data-proxy/Cargo.toml` | Data Nexus Rust workspace |
| `data-proxy/cmd/pisa` | 可执行程序（Cargo package `data-proxy`，binary `proxy`） |
| `data-proxy/gateway/core` | 协议中立网关、安全策略与审计核心 |
| `data-proxy/runtime/gateway` | MySQL/PostgreSQL 运行时与数据热路径 |
| `data-proxy/http` | Admin API 与 Portal API |
| `data-ui/` | Nuxt 管理界面 |
| `todo.md` | 唯一开发看板与下一任务 |
| `todo-impl.md` | 已交付功能归档 |

## 工具链

- Rust `1.94.1`，由 `data-proxy/rust-toolchain.toml` 固定。
- Cargo 构建产物写入 `/Volumes/fushilu/.caches/data-nexus/cargo-target`。
- `.cargo/config.toml` 与 `data-proxy/.cargo/config.toml` 均固定该缓存目录。
- 环境变量 `CARGO_TARGET_DIR` 的优先级高于配置文件；执行项目命令时不得把它指向
  其他目录。

```shell
cd data-proxy
CARGO_TARGET_DIR=/Volumes/fushilu/.caches/data-nexus/cargo-target \
  cargo build --package data-proxy --bin proxy
CARGO_TARGET_DIR=/Volumes/fushilu/.caches/data-nexus/cargo-target \
  cargo test --workspace
```

## 开发流程

开始任务前阅读 [`todo.md`](todo.md) 和
[`.claude/rules/data-nexus-development.md`](.claude/rules/data-nexus-development.md)。
每个独立功能需完成相关单测或 smoke、更新看板，并独立提交。
