# Data Nexus 开发规划

本文件是 Data Nexus 的**未完成任务看板**。已交付的切片和提交记录统一见
[`todo-impl.md`](todo-impl.md)；不在本文件重复复制历史实现。

## 0. 使用规则与工具链

- Data Nexus 当前实现是 Rust workspace，目录名 `data-proxy/` 只是历史目录名，
  不是另一个产品。
- Rust 工具链固定为 `1.94.1`，以 [`data-proxy/rust-toolchain.toml`](data-proxy/rust-toolchain.toml)
  为准；不使用仓颉工具链。仓颉 SDK 仅在未来确有 SDK 兼容需求时保留，不能作为本项目
  binary 的构建前置条件。
- 所有 Cargo 命令必须在 `data-proxy/` 中执行，并显式使用：
  `/Volumes/fushilu/.caches/data-nexus/cargo-target`。
- 所有编译、测试、smoke、覆盖率和临时导出物必须写入
  `/Volumes/fushilu/.caches/data-nexus/` 的子目录，不得在仓库内生成大体积 target 或输出物。
- 每个独立功能单独提交，提交标题必须带任务 ID；完成整项后从本文件删除，迁入
  [`todo-impl.md`](todo-impl.md)。本文件不保留 `- [x]`。
- 只有一个 `NOW` 任务。其他任务可以并行准备，但不得把“设计完成”当成“实现完成”。

常用本机门禁：

```bash
cd data-proxy
CARGO_TARGET_DIR=/Volumes/fushilu/.caches/data-nexus/cargo-target \
  cargo check --workspace
./examples/run-smoke-matrix.sh default
./examples/run-smoke-matrix.sh all
./examples/run-smoke-matrix.sh cedar
```

`cedar` 仅在启用 `security-cedar` feature 时运行；OpenDAL、OTel 等可选 feature
不得改变默认精简构建的行为。

## 1. NOW：A10 backend SQL `DECLARE ... WITH HOLD`

目标：在 PostgreSQL、简单查询、无数据义务的条件下，将命名游标交给同一条 backend
连接管理，使 `WITH HOLD` 能跨 `COMMIT` 存活到 `CLOSE` 或会话结束。设计稿见
[`docs/a10-backend-sql-with-hold-design.md`](docs/a10-backend-sql-with-hold-design.md)。

当前基线：网关已有进程内 `named_cursors`，支持 forward `FETCH` 和明确的
`PortalSuspended` 续读；`security.streaming.backend_sql_with_hold=true` 当前会被
`validate()` 拒绝，`remainders.backend_sql_with_hold=false` 必须保持诚实。

- [ ] **A10-1 实现 PG backend 游标路由**：在无 mask、row filter、watermark、
  max_rows 等义务时，把 `DECLARE`、`FETCH`、`CLOSE` 发送到同一 backend lease，
  并保证连接在游标生命周期内不会回池复用。
- [ ] **A10-2 完成事务和会话生命周期**：验证无 `WITH HOLD` 的游标在 `COMMIT`
  后失效，有 `WITH HOLD` 的游标跨 `COMMIT` 保留；`CLOSE`、`Drop`、`Quit` 清理
  backend 游标并释放连接，断连不得泄漏。
- [ ] **A10-3 处理义务冲突与配置门**：有数据义务时 fail-closed 或明确回落到
  process-local 路径；补齐错误码、日志和配置校验，禁止静默启用半成品。
- [ ] **A10-4 增加验证矩阵**：覆盖单游标、双并发游标、重复 `DECLARE`、`FETCH ALL`、
  跨 `COMMIT`、重连失效、协议错误和 backend 断开；同时覆盖安全配置开启/关闭。
- [ ] **A10-5 完成发布收口**：更新 API/UI/运维文档和 honesty helper，只有 A10-1
  至 A10-4 全部通过后才把 `remainders.backend_sql_with_hold` 改为 `true`，并运行
  默认、extended、security、xproto 全矩阵。

验收终点：真实 backend PostgreSQL smoke 能证明服务端游标跨 `COMMIT` 存活、关闭可回收，
安全义务路径不会绕过 PEP；所有 Cargo 与测试产物都位于外置缓存目录。

## 2. P0：当前发布阻塞

### A06：Backend 到 PEP 的精确窗口内存证明

当前基线：MySQL/PG `RowStream`、encode 逻辑 `peak_window_rows/bytes`、双协议多窗口
smoke 和粗粒度 RSS/cgroup cap 已有；逻辑高水位是当前权威指标，
`remainders.process_rss_window_byte_ci=false` 仍需保持。

- [ ] **A06-1 建立可重复的进程/cgroup 测量夹具**：固定数据规模、窗口大小、并发度、
  allocator/采样周期，分别覆盖 Linux cgroup、`/proc` 和 macOS 可用采样方式。
- [ ] **A06-2 增加精确窗口字节 CI**：证明 steady-state 峰值接近 1～2 个窗口，
  同时断言没有完整结果集物化；区分 encode payload、进程 RSS 和 OS 噪声。
- [ ] **A06-3 补齐双协议和失败路径**：MySQL、PostgreSQL、事务、mask、长字段、空结果、
  控制语句、客户端提前断开均有边界测试和可诊断失败信息。
- [ ] **A06-4 完成诚实字段切换**：测量门禁稳定后才更新 `remainders`、metrics、UI、
  smoke 文档和架构文；在此之前不得把逻辑 peak 宣传成 RSS 证明。

验收终点：CI 可在固定运行环境中稳定给出 1～2 窗字节结论，或明确记录受 OS/allocator
影响的不可证明边界；默认安全关闭路径和 v1 行为不回归。

### A08：PostgreSQL wire 透传与 backend TLS 完整性

当前基线：idle pool、事务 lease、双协议 TLS、PG simple Query 透传，以及 extended
原包/重编码/Streaming demote 路径已交付；义务路径已强制 Streaming。

- [ ] **A08-1 解决 Streaming 与 pool 的生命周期契约**：明确何时可复用连接、何时必须
  独占 lease，覆盖 PortalSuspended、多 Execute、事务和客户端断连。
- [ ] **A08-2 完成 PostgreSQL extended wire 矩阵**：Parse/Bind/Describe/Execute/
  Sync、多 Execute 连续帧、参数重写、ReadyForQuery、错误和回落路径都要有协议级断言。
- [ ] **A08-3 完成 backend TLS 生产门禁**：校验证书/CA、hostname、require TLS、
  不支持 TLS 的 backend 回落策略；配置错误必须 fail-closed，并覆盖 MySQL 与 PG。
- [ ] **A08-4 固化透传诚实观测**：区分 `passthrough_client`、`passthrough_extended`、
  `streaming_demote` 和重编码，检查字节计数、watermark、mask/row-filter 不被绕过。

验收终点：默认、TLS、extended、事务、跨协议 portal、义务路径 smoke 全通过，且连接
归还/释放没有泄漏或跨请求污染。

### A09：Portal 端到端流式

当前基线：NDJSON、CSV、JSON 的 `backend_window`、Complete `chunked` 回退、同协议和
跨协议 portal smoke、`x-data-nexus-window-rows` 及 PORTAL_STREAM/CHUNKED 观测已存在。

- [ ] **A09-1 消除可消除的 Complete 物化**：为 portal 的 backend 无 RowStream、空结果、
  控制语句和 INSERT/UPDATE 等路径定义清晰边界；能用窗口传输的路径不得先聚合完整结果。
- [ ] **A09-2 完成三格式一致性**：NDJSON、JSON 分片、CSV 在同协议及 PG↔MySQL 双向
  portal 中保持窗口、顺序、错误、响应头和结束帧一致。
- [ ] **A09-3 增加端到端资源验证**：HTTP 和 xproto 均检查窗口上限、逻辑 peak、断连取消、
  backend lease 回收和审计不阻塞查询。
- [ ] **A09-4 收口 UI、metrics 与文档**：明确 `backend_window` 与 `chunked` 的差异，
  不把 HTTP 分块或逻辑 peak 宣称为 backend 真流式/RSS 证明。

验收终点：portal smoke 在双协议、三格式、事务/错误/断连矩阵中通过，流式响应不发生
无界累积，所有已知限制都有对应 API/UI honesty 字段。

### SQLT：SQL 类型、协议与策略全量测试矩阵

测试规划见 [`docs/sql-test-matrix.md`](docs/sql-test-matrix.md)。本专项横跨 A06/A08/A09/
A10/T01，不替代各功能实现；它负责用统一 case manifest、真实 backend oracle 和分层矩阵
证明“支持、改写、拒绝、不支持”四类行为。首版最低 230 个 canonical SQL case，展开后
PR/nightly/release 分别不少于 350/1,500/3,000 次执行。

- [ ] **SQLT-3 完成 SQL corpus**：至少覆盖会话/元数据 20、DQL 80、DML 35、DDL 30、
  TCL/prepared/cursor 35、非法/恶意/unsupported 30；每个适用家族包含 allow、rewrite、
  deny、unsupported 和副作用断言。
- [ ] **SQLT-4 完成 wire 与跨协议矩阵**：覆盖 MySQL text/binary prepared、PG simple/
  extended、HTTP portal、xproto，以及 MySQL/MySQL、PG/PG、MySQL/PG、PG/MySQL；A08/A09/
  A10/T01 高风险组合全量运行，其余维度使用可审计 pairwise。
- [ ] **SQLT-5 完成治理与故障矩阵**：覆盖 security off、allow/deny、column strip、mask、
  row filter、watermark、max rows、ticket、Remote PDP/Cedar、审计 L0/L1/L2，以及取消、
  断连、backend 重启、pool/lease 回收、长字段和大结果有界性。
- [ ] **SQLT-6 接入分层门禁与报告**：新增 parser/command/mysql-wire/pg-wire/nightly/
  release 分组，输出 manifest/results/normalized-output/audit/metrics/logs/summary；PR 快速失败，
  nightly 扩展覆盖，release 禁止 unknown 和无原因 skip。

验收终点：不少于 230 个 canonical cases 和 3,000 次发布矩阵执行全部得到结构化结果；
成功路径与直连 oracle 等价，拒绝/unsupported 无后端副作用，事务、审计、metrics 和资源
回收断言通过，失败可用单个 case ID 稳定复现。

## 3. P1：产品重债

### H05：多实例状态与 Vault 内存边界

当前基线：file+lock、AES-GCM、mtime 热更、全文件 last-writer-wins、密码 ZeroizeOnDrop
和 UI/API honesty 已交付；当前明确不是 CRDT，也不是 `mlock` 安全堆。

- [ ] **H05-1 实现并发状态 merge**：定义字段级冲突策略、版本/时间戳语义、删除与重放规则，
  用两个以上实例并发写入验证不会静默丢更新；兼容旧 LWW 文件格式。
- [ ] **H05-2 评估并实现敏感内存锁定**：在目标平台验证 `mlock`/等价能力、失败策略、
  fork/core dump/swap 风险和资源释放；无法可靠保证时继续保持 `mlock=false`。
- [ ] **H05-3 补齐生产故障演练**：锁竞争、进程崩溃、半写文件、密钥错误、重启恢复、
  revoke/prune/Drop 后擦除均有可重复测试和 runbook。
- [ ] **H05-4 完成诚实收口**：只有实现和跨实例测试达标才更新 `crdt`/`mlock` 字段、
  UI、配置模板和架构文档。

验收终点：多实例并发不会产生未记录的数据丢失，Vault 密码生命周期和异常恢复有证据；
不能证明的能力继续显式标记为 false。

### B08：L2 样本与大 payload 生产门禁

当前基线：样本默认关闭、L2 强制门、rows/bytes 有界、截断标记、API/UI honesty 和
smoke 已有；OpenDAL 上传仍是可选 feature，不能宣传为全量 L3 归档。

- [ ] **B08-1 完成样本存储后端边界**：明确本地落盘、OpenDAL、失败重试、保留期、权限、
  加密和删除语义；上传失败不得阻塞查询或伪报成功。
- [ ] **B08-2 建立生产样本门禁**：以真实大 payload、并发、磁盘满、对象存储不可用、
  超时和截断场景验证 rows/bytes 上限、审计级别和敏感字段处理。
- [ ] **B08-3 固化运维与产品表达**：默认关闭、高 QPS 限制、非全量 L3、非完整结果归档
  在模板、runbook、API、UI 和 smoke 断言中保持一致。

验收终点：样本数据有界、可追踪、可清理，任何存储失败都可观测且不绕过审计/PEP 策略。

### T01：列 ACL 与复杂 SQL

当前基线：表提取、WHERE/HAVING/EXISTS/IN/标量子查询、嵌套 SELECT 列 strip 和 wildcard
拒绝/诚实字段已覆盖；`*`、`t.*`、alias `e.*` 不展开。

- [ ] **T01-1 明确 wildcard 策略终点**：决定 allow 模式是继续不展开并保守放行，还是实现
  catalog 驱动展开；不得在未实现列集合推导时静默 strip 或放行隐式列。
- [ ] **T01-2 补齐复杂 AST**：覆盖多层相关子查询、CTE、窗口函数、集合运算、函数表达式、
  方言差异、别名遮蔽和重复列名；无法安全重写时 fail-closed。
- [ ] **T01-3 完成协议级 E2E**：MySQL/PG、prepared/simple、跨协议 portal 和 deny/allow
  策略均验证返回列集合、错误码、审计事件和不泄露原始敏感列。

验收终点：支持的 AST 集合有明确清单和测试覆盖，未支持的 SQL 稳定拒绝或明确降级，
`star_expands_wildcard` 等 honesty 字段与真实行为一致。

## 4. P2：外部环境验收

### H04b：OIDC 联调与部署验收

本项拆为「仓库代码验收」和「生产部署验收」。本地 Docker 栈使用 Keycloak、HTTPS edge、
data-ui 和 Rust gateway，能够真实执行 OIDC Authorization Code + PKCE、回调、JWKS、
issuer/audience/expiry、角色映射和登出；它不是把 localhost 冒充生产，而是完整验证仓库内
协议与代码行为。香港云服务器不是 Data Nexus 的代码依赖，也不是关闭代码侧 H04b 的前置条件。

- [x] **H04b-1 本地 Docker 验收栈**：`data-proxy/examples/smoke-h04b-docker.sh` 使用外置
  缓存构建 Rust gateway 和 OIDC-enabled data-ui，并以本地 CA 提供四个 HTTPS host。
- [x] **H04b-2 本地真实 OIDC 流程**：Keycloak discovery、Authorization Code + PKCE、
  浏览器回调、state/PKCE verifier、token exchange、JWKS、issuer/audience/expiry 校验和
  end-session logout 均已执行；`/admin/me` 使用 Bearer access token 返回 200。
- [x] **H04b-3 本地角色与拒绝路径**：已覆盖 viewer/operator/admin、未知角色、缺少角色、
  过期 token、错误 issuer、错误/缺失 audience、无 token 和未授权 reload。
- [ ] **H04b-4 生产部署验收**：在外部 HTTPS 环境配置公共 DNS、受信任 CA、真实 IdP tenant、
  外部防火墙、secret 注入、时钟同步和日志脱敏；留存脱敏部署证据与回滚步骤，secrets 不进 Git。

仓库代码验收终点：本地 Docker + 浏览器验收报告通过即可关闭代码侧 H04b。生产验收终点：
真实外部 IdP 到真实部署的回调和角色映射闭环完成；公共 DNS、受信任 CA、网络边界和生产
secrets 仍必须单独验收。

## 5. P3：明确后置，不纳入当前版本

这些项目保留在规划中，但没有排入当前发布关键路径；除非重新确认范围和优先级，不得以零散
代码或文档变更宣称完成。

- [ ] **F30** 敏感识别增强：在现有 `column_tags`/mask 之外定义可审计的识别规则、误报/漏报
  评估、性能预算和数据处理边界；非目标是全量 DLP。
- [ ] **P01** 新协议：先完成 Redis 等协议的需求、威胁模型、协议兼容范围和维护成本评估。
- [ ] **P02** 深终端 Agent：后置；先明确部署模型、权限边界、升级和离线行为。
- [ ] **P03** 审计 Parquet/分析：评估 Parquet/DataFusion 的 schema、冷热存储、查询隔离和
  成本；不得影响审计写入热路径。
- [ ] **P04** Sharding rewrite：补齐 `gateway_core` stub 的路由、事务一致性、重试和故障语义，
  未有完整设计前不实现半成品。

## 6. 通用完成标准

每个主任务的所有未完成子项都满足后，才允许从看板移入归档：

- [ ] 有针对行为的 unit/integration/smoke 测试，失败信息能定位到协议、策略或资源边界。
- [ ] 运行相关 `cargo test`、`cargo check` 和 feature 矩阵；默认构建、`security.enabled=false`
  与 v1 L0 行为不回归。
- [ ] 更新必要的 API/UI、metrics、runbook、架构文档和 honesty 字段；未实现能力必须
  fail-closed 或显式标记，不得静默 no-op。
- [ ] 所有产物位于 `/Volumes/fushilu/.caches/data-nexus/` 子目录，工作树没有生成大体积构建目录。
- [ ] 完成本任务独立 Git commit，提交标题包含任务 ID；再从本文件删除对应条目并写入
  `todo-impl.md`。

## 7. 已知诚实边界

在对应任务完成前，以下字段必须保持 false 或对应的保守语义：

| 能力 | 当前诚实状态 |
|------|--------------|
| A10 backend `DECLARE ... WITH HOLD` | 仅进程内命名游标；`remainders.backend_sql_with_hold=false` |
| H05 CRDT merge | 全文件 LWW；`remainders.crdt_merge=false` |
| H05 mlock | Zeroize 但活跃密码仍在进程 RAM；`remainders.mlock=false` |
| A06 精确 RSS/cgroup 1～2 窗字节 CI | 逻辑 `peak_window_*` 权威；`remainders.process_rss_window_byte_ci=false` |
| A09 Complete/无 RowStream | 允许有限回退到 `chunked` 或小结果物化；不得称作 backend_window |
| B08 样本 | 默认关闭、有界、L2；非全量 L3 合规归档 |
| T01 wildcard | 不展开 `*`/`t.*`/alias wildcard；无法安全判断时拒绝 |

详细架构约束见 [`docs/data-nexus-tech-architecture-2026.md`](docs/data-nexus-tech-architecture-2026.md)
§13.3、[`docs/data-audit-architecture.md`](docs/data-audit-architecture.md) 和
[`docs/data-security-roadmap.md`](docs/data-security-roadmap.md)。
