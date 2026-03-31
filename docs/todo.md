# Bollydog 后续设计与增强（来自 fit 分析与架构讨论）

## 待实现（本阶段未做）

- **Exchange 发布 Command**：在 Exchange（或 Hub）侧暴露一个 **BaseCommand**，用于将人工/运维注入的事件发布到 Exchange（与 `hub.emit` 互补，可走统一入口与审计）。当前版本仅 `hub.emit` + `_process_message` 完成后 publish。

## L0 核心

- destination 路由语义完善（P1）
- `@timer` / `@cron`（P2）
- `hub.get_service(cls)`（P2）
- Service 级 `@handle(CommandClass)`（P3）

## L2 编排

- Thread 多轮会话（P0）
- Middleware 链（P0）
- Parallel 扇出聚合（P0）
- Handoff（P1）
- capabilities 声明（P1）

## L1 分布式

- Transport（P0）
- Registry（P0）
- RemoteDispatch（P0）
- Event Federation（P1）
- Envelope 序列化（P0）
- Hub Identity（P0）
- 负载均衡（P1）

## L3 Agent

- Tool + MCP（P1）
- 分层 Memory（P2）
- 声明式 DAG（P3）

详见 `timing/ANALYSIS_BOLLYDOG_FIT.md`。
