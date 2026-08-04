# SQL 全量测试矩阵规划

当前已交付 SQLT-1 的首批规范资产：`data-proxy/examples/sql-matrix/` 下的能力注册表、
13 个独立 SQL case 文件、显式 policy outcome manifest，以及零依赖校验器和单元测试。
后续 SQLT-2 至 SQLT-6 继续在此基础上补齐 Docker fixture、backend oracle、230+ case
corpus、wire/策略故障矩阵与分层报告门禁。

本文定义 Data Nexus 的 SQL 行为测试范围。目标不是证明每一种数据库方言都能被
跨协议翻译，而是对每一种输入明确记录以下四类结果之一：

1. **允许且语义正确**：结果、错误、事务状态、审计和资源回收都符合预期。
2. **允许但改写/降级**：记录原始与有效 SQL、改写原因和对应的 honesty 字段。
3. **策略拒绝**：返回稳定的拒绝错误，产生审计事件，不执行后端副作用。
4. **能力不支持**：在能力清单中显式标记，稳定 fail-closed，不静默透传或伪成功。

“解析成功”不能作为测试通过标准；必须验证后端语义、wire 响应、会话状态、审计和
资源生命周期。

## 1. 测试分层

| 层级 | 目标 | 运行内容 | 门禁 |
| --- | --- | --- | --- |
| L0 parser/unit | 解析、分类、对象提取、参数和错误位置 | 每类 SQL 的最小/边界/非法样例 | PR 必须通过 |
| L1 command | `GatewayCommand`、PDP、改写和结果编码契约 | 同协议内存 backend，覆盖 allow/deny/rewrite | PR 必须通过 |
| L2 protocol | wire 协议和会话状态 | MySQL text/binary、PG simple/extended、prepared | PR 必须通过 |
| L3 backend E2E | 真实数据库语义 | MySQL 与 PostgreSQL 容器，固定 schema/seed | nightly extended |
| L4 cross-protocol | 有限翻译子集和拒绝边界 | MySQL -> PG、PG -> MySQL、portal | nightly extended |
| L5 resource/failure | 流式、取消、连接池、审计背压和故障 | 大结果、断连、backend 重启、磁盘/网络故障 | 发布前 |

L0/L1 负责快速定位；L2/L3/L4 不得用 parser 通过替代真实执行。L5 的资源数字允许有
平台噪声，但必须验证有界、可回收和 honesty 字段没有被误报。

## 2. SQL 语句类型清单

每个类别至少有：最小成功样例、带参数样例、空结果样例、错误样例、权限拒绝样例、
大结果/长字段样例（适用时）、多语句或连续帧样例（适用时）。

首版 canonical corpus 的最低预算如下。这里的 case 是独立 SQL 语义，不包含协议、策略和
事务维度展开后的执行次数：

| 家族 | 最低 canonical cases | 说明 |
| --- | ---: | --- |
| 会话、元数据、诊断 | 20 | USE/SET/SHOW/DESCRIBE/EXPLAIN/能力拒绝 |
| DQL | 80 | 基础查询、连接、聚合、子查询、CTE、集合、窗口、函数、锁、wildcard |
| DML | 35 | INSERT/UPDATE/DELETE/MERGE/RETURNING/方言 upsert |
| DDL | 30 | table/index/view/schema/sequence/临时对象和事务差异 |
| TCL、prepared、cursor | 35 | transaction/savepoint/prepared/extended/cursor/多语句 |
| 非法、恶意和 unsupported | 30 | 语法错、类型错、注入边界、超限、方言不支持 |
| **合计** | **至少 230** | 每个 case 都必须有稳定 ID 和预期分类 |

展开后的最低执行预算：PR 快速矩阵不少于 350 次，nightly 不少于 1,500 次，发布候选
全矩阵不少于 3,000 次。数字只用于防止覆盖缩水，不代替语义覆盖；同一个 `SELECT 1`
重复三千次不计为全量。

### 2.1 会话与元数据

- `PING`、连接初始化、认证失败、`QUIT`。
- `USE`、`SET`、`RESET`、`SET NAMES`、时区/隔离级别/只读属性。
- MySQL `SHOW DATABASES/TABLES/TABLE STATUS/COLUMNS/CREATE TABLE`、`DESCRIBE`。
- PostgreSQL `SHOW`、`SET`、`current_schema()`、系统 catalog 的只读查询。
- `EXPLAIN`、`EXPLAIN ANALYZE` 的允许、拒绝和结果形态；禁止把诊断语句当普通 DQL。
- 不支持或高风险的 `LOAD DATA`、`COPY`、`COPY ... PROGRAM`、`VACUUM`、`ANALYZE`、
  `CALL`、`DO` 等必须有明确能力标签和 fail-closed 断言。

### 2.2 DQL：查询

- 基础 `SELECT`：常量、列、别名、`DISTINCT`、`NULL`、布尔值、表达式和参数。
- 过滤：`WHERE`、`IN`、`EXISTS`、`BETWEEN`、`LIKE/ILIKE`、正则、三值逻辑。
- 聚合：`COUNT/SUM/AVG/MIN/MAX`、`GROUP BY`、`HAVING`、空组和 `NULL` 聚合。
- 排序分页：多列 `ORDER BY`、`NULLS FIRST/LAST`、`LIMIT/OFFSET`、稳定顺序。
- 连接：INNER/LEFT/RIGHT/FULL/CROSS、USING、自然连接、重复列名和别名遮蔽。
- 子查询：标量、相关、嵌套、派生表、`EXISTS/IN`、多层作用域。
- CTE：普通、递归、多个 CTE、CTE 中的 DML（按方言能力标记）。
- 集合运算：`UNION/UNION ALL/INTERSECT/EXCEPT`、排序和列类型兼容性。
- 窗口：`OVER`、partition/order/frame、排名、偏移、窗口与聚合组合。
- 函数与类型：字符串、数值、日期时间、JSON、数组/集合、正则、方言专有函数。
- 锁与并发读取：`FOR UPDATE`、`FOR SHARE`、`NOWAIT/SKIP LOCKED`，不支持时拒绝。
- wildcard：`*`、`t.*`、alias wildcard；验证列 ACL、列裁剪、元数据不足时的拒绝。

### 2.3 DML：数据变更

- `INSERT ... VALUES`：单行、多行、默认值、`NULL`、参数、类型转换和约束错误。
- `INSERT ... SELECT`、`INSERT ... ON CONFLICT`、MySQL `ON DUPLICATE KEY UPDATE`。
- PostgreSQL `RETURNING` 和 MySQL 等价能力；跨协议不支持时明确拒绝。
- `UPDATE`：有/无顶层 `WHERE`、表达式更新、连接更新、子查询更新、返回结果。
- `DELETE`：有/无顶层 `WHERE`、连接删除、子查询删除、级联约束错误。
- `MERGE`（支持的方言）、`REPLACE`、`TRUNCATE` 等方言差异单独标记。
- 每个写操作验证：影响行数、约束错误、事务状态、审批/ticket、审计和重试语义。

### 2.4 DDL 与对象生命周期

- `CREATE/DROP/ALTER TABLE`：列、默认值、约束、索引、主键、外键和命名冲突。
- `CREATE/DROP INDEX`、`CREATE/DROP VIEW`、schema/database、sequence（按方言）。
- `RENAME`、`TRUNCATE`、`COMMENT`、临时表和临时对象生命周期。
- DDL 在事务中的提交/回滚差异，隐式提交差异，锁和并发冲突。
- DDL 需要审批、被策略拒绝、对象不存在、权限不足时必须无副作用且可审计。

### 2.5 TCL、prepared、cursor 与多语句

- `BEGIN/START TRANSACTION`、`COMMIT`、`ROLLBACK`、`SAVEPOINT`、`ROLLBACK TO`、
  `RELEASE SAVEPOINT`、隔离级别和只读事务。
- MySQL prepared statement：prepare/execute/close、参数数量/类型/NULL/重复执行。
- PostgreSQL extended wire：`Parse/Bind/Describe/Execute/Sync`、多 portal、参数重写、
  `ReadyForQuery`、错误后同步恢复。
- `DECLARE/FETCH/CLOSE`、`FETCH ALL`、重复声明、双游标、会话结束清理；A10 另测
  `WITH HOLD` 跨 `COMMIT` 与无 HOLD 的失效边界。
- 多语句、连续请求、一个事务内多次执行、错误后继续执行；协议允许性必须按 frontend
  明确，禁止把客户端拼接多语句误当成单语句。

## 3. SQL 值、标识符与结果形态

### 3.1 值和编码

- `NULL`、空字符串、空二进制、UTF-8/非 ASCII、引号和反斜杠。
- 有符号/无符号整数、精确 decimal、浮点 NaN/Infinity（按 backend 能力）、溢出。
- `DATE/TIME/TIMESTAMP`、时区、闰日、微秒、DST 边界。
- `CHAR/VARCHAR/TEXT`、BLOB/BYTEA、JSON、UUID、数组、枚举、二进制协议编码。
- 0 行、1 行、窗口边界行、超大行、超大列、重复列名、无列结果和多结果集。

### 3.2 标识符和文本

- 未引用、反引号、双引号、大小写折叠、schema/database/table/column 完全限定名。
- 保留字、Unicode 标识符、长标识符、点号和别名遮蔽。
- 注释、换行、大小写、尾部分号、空白和参数占位符的归一化不会改变语义。
- 原始 SQL、改写 SQL、fingerprint 和审计载荷必须脱敏并保持可关联。

## 4. 测试维度矩阵

每个 SQL case 使用 manifest 声明维度；不是每个 case 都需要笛卡尔积，但以下组合必须
由 pairwise 或专项套件覆盖：

| 维度 | 值 |
| --- | --- |
| frontend/backend | MySQL/MySQL、PG/PG、MySQL/PG、PG/MySQL |
| frontend protocol | MySQL text、MySQL binary prepared、PG simple、PG extended、HTTP portal、xproto |
| execution mode | autocommit、explicit transaction、savepoint、streaming、portal、prepared |
| policy | security off、allow、deny、column strip、mask、row filter、watermark、max rows、ticket、remote PDP/Cedar |
| result | 0/1/many rows、large row、multi-result、error、cancel、PortalSuspended |
| backend state | healthy、pool reuse、exclusive lease、transaction lease、backend reset/restart |
| client state | normal close、error recovery、timeout、early disconnect、duplicate request |
| observability | audit L0/L1/L2、metrics path、rewrite fingerprint、decision/obligation |

### 必须全量组合

以下组合不能只用 pairwise，必须对清单中的适用 SQL 全跑：

- A10 cursor：PG/PG + simple/extended + autocommit/transaction + no-HOLD/HOLD。
- A08 extended wire：PG/PG + Parse/Bind/Describe/Execute/Sync + 多 Execute/错误恢复。
- A09 portal：四种 frontend/backend 方向 + 三种输出格式 + streaming/chunked + 断连。
- T01 列 ACL：SELECT/DML + wildcard/子查询/CTE/窗口 + allow/deny/mask/row filter。
- A06 资源：MySQL/PG + 有/无义务 + 小/窗口边界/大结果 + 正常/取消/断连。
- DDL/TCL：同协议真实 backend + autocommit/显式事务 + allow/审批/deny。

## 5. Case manifest 与断言

每个 case 应记录为结构化 manifest（推荐 JSON/YAML），至少包含：

```yaml
id: sql-select-join-001
family: dql.join
sql: "SELECT ..."
dialect: postgres
frontend: pg_extended
backend: postgres
params: []
transaction: explicit
policy: allow
expected:
  decision: allow
  result_shape: rows
  error: null
  audit_action: query
  rewrite: false
  bounded_rows: true
```

断言分为四层：

1. **协议**：握手、请求帧、响应帧、错误码、参数类型、`ReadyForQuery`/结束帧。
2. **语义**：与直连 backend 的规范化结果、影响行数、事务状态和 schema 状态比较。
3. **治理**：decision、义务、原始/有效 fingerprint、审计级别、敏感值不泄漏。
4. **资源**：窗口上限、峰值逻辑字节、连接 lease、pool 回收、取消传播、无后台任务泄漏。

允许结果不能只比较字符串；结果比较应规范化列名、类型、NULL、时区、二进制和排序
语义。没有稳定顺序的查询必须显式加排序，或只比较集合/计数。

## 6. 执行分组与产物

建议新增 `examples/run-sql-matrix.sh`，分组如下：

- `parser`：L0 parser/unit，PR 快速运行。
- `command`：L1 PDP/rewrite/encode，PR 默认运行。
- `mysql-wire`、`pg-wire`：同协议 L2，PR 默认运行。
- `dml-ddl-tcl`：真实 backend 的写入、结构和事务语义，nightly。
- `pg-extended-cursor`：A08/A10 专项，nightly。
- `portal-cross-protocol`：A09 四方向、三格式、资源断言，nightly。
- `security-sql`：T01、mask、row filter、watermark、ticket、audit，nightly。
- `resource-failure`：A06/L5，发布前或专用 Linux runner。
- `all`：上述全部，发布候选门禁。

固定输出根目录：

```text
/Volumes/fushilu/.caches/data-nexus/sql-matrix/<run-id>/
```

每次运行至少生成 `manifest.jsonl`、`results.jsonl`、`normalized-output/`、`audit/`、
`metrics/`、`logs/` 和 `summary.txt`。失败 case 必须保存脱敏请求、响应、backend 对照
结果、配置摘要和复现命令，不保存生产 secrets 或完整敏感结果。

## 7. 完成标准

- 每个 SQL 家族都有 allow、rewrite/demote、deny、unsupported 样例（适用者必须覆盖）。
- MySQL/PG 同协议、四个跨协议方向、MySQL text/binary、PG simple/extended/HTTP/xproto
  的适用矩阵有结果记录。
- 事务、prepared、cursor、portal、streaming、取消、断连和 backend 故障有独立断言。
- 直连对照结果、错误语义、审计、metrics、资源回收全部通过。
- 不支持的 SQL 有稳定错误和文档清单；不能以“后端碰巧接受”作为网关支持证据。
- canonical corpus 不少于 230 个独立 case，PR/nightly/release 执行预算分别达到
  350/1,500/3,000；新增 SQL 能力必须同步增加 manifest 和对照断言。
- summary 按 SQL 家族、协议、backend、策略和结果分类报告覆盖率；`unknown` 为零，
  `skip` 必须包含 issue、能力标签和到期条件，发布门禁禁止无原因 skip。
- 所有构建、测试和导出物位于 `/Volumes/fushilu/.caches/data-nexus/`，并有独立 Git commit。
