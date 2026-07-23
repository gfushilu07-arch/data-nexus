# A10 backend SQL `DECLARE … WITH HOLD` — 设计稿（未实现）

状态：**未实现**。配置 `security.streaming.backend_sql_with_hold=true` 在 `validate()` **拒绝**（防静默 no-op）。  
Admin：`streaming.backend_sql_with_hold=false`（镜像配置）+ `remainders.backend_sql_with_hold=false`。  
今日路径：进程内 `named_cursors`（`core_engine::handle_named_cursor_sql`）。

## 目标

在 **PostgreSQL 简单查询** 且 **无结果义务** 时，将：

```sql
DECLARE c CURSOR WITH HOLD FOR SELECT …;
FETCH n FROM c;
CLOSE c;
```

转发为 backend 服务端游标（`WITH HOLD` 跨 COMMIT 存活至 CLOSE / 断连），而不是网关进程内 `RowStream`。

## 非目标（首刀）

- MySQL 服务端游标  
- 有 mask / row_filter / watermark / max_rows 时的 Secure 路径（仍进程内或拒绝）  
- MOVE / ABSOLUTE / BACKWARD  
- 跨协议 portal DECLARE  

## 建议切片

| 步 | 内容 | 验收 |
|----|------|------|
| 0 | 配置门 + 设计稿 + 诚实 API（**本切片**） | `validate` 拒 true；unit + config-validate |
| 1 | PG 无义务：DECLARE/FETCH/CLOSE → backend SQL on pool/tcp lease | smoke：WITH HOLD 跨 COMMIT；断连 backend CLOSE |
| 2 | 事务边界：无 HOLD 在 COMMIT 丢弃；有 HOLD 保留 backend 游标 | 扩展 stream smoke |
| 3 | 会话 Drop/Quit：backend `CLOSE ALL` / 连接释放 | 无泄漏 |
| 4 | 义务冲突：有 mask 时 fail-closed 或强制 process-local | 明确错误码 |
| 5 | `remainders.backend_sql_with_hold=true` 仅当步 1–3 达标 | 翻转诚实字段 + 全矩阵 |

## 运行时草图

1. `parse_named_cursor_sql` 不变。  
2. `handle_named_cursor_sql`：若 `backend_sql_with_hold && PG && 无义务` → `backend.execute("DECLARE …")` 持有 **同一 backend 连接** 直至 CLOSE/会话结束。  
3. FETCH → `FETCH n FROM name` on that connection；结果仍经 encode 路径（非 wire 透传义务）。  
4. 否则 → 今日 process-local 路径。

## 风险

- 连接占用：每个打开游标占一条 backend 连接（池压力）。  
- 与 passthrough `tcp_txn` 生命周期交织。  
- 策略：DECLARE 文本 vs 内层 SELECT 的 PDP 对象抽取需明确。

## 相关

- `todo.md` A10  
- `examples/assert-security-policies-honesty.py`  
- `gateway_core::SecurityStreamingConfig::backend_sql_with_hold`
