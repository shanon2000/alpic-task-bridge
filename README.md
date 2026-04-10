# Alpic Task Bridge

最小可用版本的任务桥系统。建立外部 AI（大脑）→ 任务桥 → 本地 Worker 的单向链路。

**这不是自治 Agent，不是通用执行器，不是浏览器自动化工具。**

---

## 架构

```
[外部客户端 / ChatGPT / Claude Desktop / Alpic]
         │
         │ MCP (streamable-http)
         ▼
alpic-mcp (MCP Server)  ──HTTP──►  alpic-bridge (Task Bridge API)
                                     │
                                     ▼
                               alpic-worker (执行端)
```

## 组件

| 目录 | 作用 | 启动入口 |
|---|---|---|
| `alpic-mcp/` | MCP 协议包装，对外暴露工具 | `server.py remote` |
| `alpic-bridge/` | 任务存储/分发 HTTP API | `bridge.py` |
| `alpic-worker/` | 定时拉取并执行任务 | `worker.py` |

## 快速启动

```bash
# 终端 1：启动 Bridge
cd alpic-bridge && python bridge.py

# 终端 2：启动 Worker
cd alpic-worker && python worker.py

# 终端 3：启动 MCP 远程服务
cd alpic-mcp && python server.py remote

# 终端 3（可选）：运行 demo
cd alpic-bridge && python demo.py
```

## 支持的 task_type

| task_type | 说明 |
|---|---|
| `write_file` | 写入文件到白名单目录 |
| `run_python` | 执行白名单目录内的 .py 脚本 |
| `run_shell_safe` | 执行白名单命令（仅 python/py） |

## 安全说明

- Bridge 和 Worker 的 token 必须一致
- MCP Server 通过 Bearer Token 访问 Bridge
- 部署前修改所有默认 token
- 查看 [alpic-mcp/README.md](./alpic-mcp/README.md) 了解 MCP 部署详情

## 版本历史

| 版本 | 说明 |
|---|---|
| V1 | 最小可用版本，3种 task_type |
| V1.1 | 安全加固：全接口鉴权、/health 增强 |
| V1.1 + MCP | 新增 MCP 远程包装层 |
