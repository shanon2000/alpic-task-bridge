# Alpic MCP Server V1.1

最小 MCP 包装层，将已有 Alpic Task Bridge V1.1 的能力通过 MCP 协议暴露给外部 AI 客户端。

**这不是独立系统。** 需要配合已运行的 Alpic Task Bridge V1.1 使用。

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

- `alpic-mcp`：MCP 协议转换，监听 8081，暴露 3 个工具
- `alpic-bridge`：任务存储/分发，监听 18080，内网访问
- `alpic-worker`：定时拉 bridge 执行任务，无需暴露

---

## 工具列表

| 工具名 | 作用 |
|---|---|
| `create_task` | 向 Bridge 创建一个新任务 |
| `get_task_status` | 查询指定 task_id 的状态和结果 |
| `get_bridge_health` | 查询 Bridge 健康状态 |

---

## 配置

编辑 `config.yaml`：

```yaml
bridge:
  base_url: "http://127.0.0.1:18080"   # Bridge 地址（远程部署时改为实际地址）
  token: "CHANGE-ME-IN-PRODUCTION"      # 必须与 bridge config 一致

server:
  transport: "streamable-http"         # 远程部署用 streamable-http
  host: "0.0.0.0"                        # 监听地址
  port: 8081                            # MCP 服务端口
```

**环境变量覆盖**（优先级高于 config.yaml）：
- `ALPIC_BRIDGE_URL`
- `ALPIC_BRIDGE_TOKEN`
- `ALPIC_TRANSPORT`
- `ALPIC_HOST`
- `ALPIC_PORT`

---

## 部署方式

### 远程模式（streamable-http）

```bash
cd alpic-mcp && python server.py remote
```

服务监听 `0.0.0.0:8081`，通过 `/mcp` 路径暴露 MCP 端点。

### 本地 stdio 模式（Claude Desktop 等）

```bash
cd alpic-mcp && python server.py
```

---

## 本地测试

**前提：Bridge 已启动。**

```bash
# 远程模式测试（需要先启动 MCP server）
cd alpic-mcp && python test_remote.py

# 工具层测试（直接调 bridge，无需启动 MCP server）
cd alpic-mcp && python test_mcp.py
```

---

## 部署说明

### 最小部署顺序

```
1. 部署 alpic-bridge（内网，仅 worker 访问）
2. 部署 alpic-worker（能访问 bridge）
3. 部署 alpic-mcp（对外暴露 MCP 端口）
```

### Token 配置

bridge 和 mcp 的 token 必须一致。部署前在两边的 config.yaml 中设置为同一个强随机字符串。

### HTTPS

MCP server 本身不支持 HTTPS。公网部署通过反向代理（Caddy / nginx）处理 TLS：
- 反向代理：`https://your-domain.com` → `http://127.0.0.1:8081`
- MCP endpoint：`https://your-domain.com/mcp`
- MCP server 仍监听 HTTP

### 与 Claude Desktop 集成（stdio 模式）

```json
{
  "mcpServers": {
    "alpic-bridge": {
      "command": "python",
      "args": ["C:/path/to/alpic-mcp/server.py"]
    }
  }
}
```

---

## 工具详细说明

### create_task

**参数：** `task_type`（必填）、`payload`（必填）
**返回：** `{"success": true, "task_id": "...", "status": "accepted"}`

### get_task_status

**参数：** `task_id`（必填）
**返回：** `{"task_id": "...", "status": "done", "summary": "...", "artifact_path": "", "stdout_tail": "", "stderr_tail": ""}`

### get_bridge_health

**参数：** 无
**返回：** `{"service": "alpic-bridge", "version": "1.1", "status": "ok", "timestamp": "..."}`

---

## 错误说明

失败时返回 JSON 错误结构：
```json
{"success": false, "error": "Cannot connect to bridge...", "http_status": null}
```

常见错误：
- `Cannot connect to bridge` — Bridge 未运行或地址错误
- `Unauthorized` — Token 不匹配
- `Task not found` — task_id 不存在
- `unsupported task_type` — 不是 write_file/run_python/run_shell_safe

---

## 当前限制

- 无内置 HTTPS（依赖反向代理）
- 无内置认证（MCP 层面依赖 Bearer Token）
- 3 个工具，无 list_tasks/cancel_task 等
- 不支持多 worker 调度
