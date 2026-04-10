# Alpic Task Bridge V1.1

最小可用版本的任务桥系统。建立 ChatGPT（大脑）→ 任务桥（中转层）→ 本地 Worker（执行端）的单向链路。

**这不是自治 Agent，不是通用执行器，不是浏览器自动化工具。**

---

## 1. 项目简介

Alpic Task Bridge V1 是一个轻量任务桥，包含两个独立服务：

- **Bridge（服务端）**：提供任务存储和分发接口
- **Worker（客户端）**：定时拉取任务、执行、回传结果

### 支持的 task_type

| task_type | 说明 |
|---|---|
| `write_file` | 写入文件到白名单目录 |
| `run_python` | 执行白名单目录内的 .py 脚本 |
| `run_shell_safe` | 执行白名单命令（仅 python/py） |

---

## 2. 目录结构

```
alpic-bridge/           # 任务桥服务端
├── bridge.py           # 主服务，4个HTTP接口
├── task_store.py       # 文件式任务存储
├── config.yaml         # 服务配置
├── test_bridge.py      # HTTP接口测试
├── test_store.py       # 存储逻辑测试
├── test_integration.py # write_file 端到端测试
├── test_run_python_integration.py  # run_python 端到端测试
├── test_run_shell_safe_integration.py # run_shell_safe 端到端测试
├── logs/               # 运行日志
└── tasks/              # 任务JSON存储

alpic-worker/           # 本地执行端
├── worker.py           # 主程序，轮询+执行+报告
├── worker_state.py     # 本地状态账本（去重/锁）
├── executors.py        # 各 task_type 执行逻辑
├── config.yaml         # Worker 配置
├── test_worker.py     # 状态/去重测试
├── test_write_file.py  # write_file 专项测试
├── test_run_python.py  # run_python 专项测试
├── test_run_shell_safe.py  # run_shell_safe 专项测试
├── state/              # 本地状态文件
│   └── worker_state.json
├── logs/               # 运行日志
├── work/               # 测试用脚本目录
│   ├── test_success.py
│   ├── test_fail.py
│   └── test_timeout.py
└── allowed_write/      # write_file 白名单目录（示例）
```

---

## 3. 环境要求

- **Python**: 3.10+
- **依赖**: PyYAML（已内置在标准环境中）
- **操作系统**: Windows/macOS/Linux（本文档以 Windows 为例）
- **网络**: Bridge 和 Worker 之间需 TCP 连通（默认 `127.0.0.1:18080`）

---

## 4. 配置说明

### Bridge (config.yaml)

```yaml
bridge:
  host: "127.0.0.1"   # 监听地址
  port: 18080         # 监听端口
  token: "alpic-v1-token"  # 简单鉴权token

storage:
  task_dir: "./tasks"  # 任务JSON存储目录
  log_dir: "./logs"
```

### Worker (config.yaml)

```yaml
worker:
  poll_interval_seconds: 5     # 轮询间隔（秒）
  bridge_url: "http://127.0.0.1:18080"
  token: "alpic-v1-token"

state:
  state_file: "./state/worker_state.json"

# 允许写文件/执行脚本的目录
allowed_dirs:
  - "./allowed_write"
  - "./temp"
  - "./work"

python:
  python_path: ""     # 空=使用 PATH 中的 python
  default_timeout_seconds: 30

shell:
  allowed_commands:   # run_shell_safe 白名单（极小）
    - "python"
    - "py"
  default_timeout_seconds: 30
```

---

## 5. 启动顺序

### 第一步：启动 Bridge

```bash
cd alpic-bridge
python bridge.py
```

Bridge 启动后监听 `http://127.0.0.1:18080`。

### 第二步：启动 Worker

```bash
cd alpic-worker
python worker.py
```

Worker 每 5 秒轮询 Bridge，拉取任务并执行。

### 第三步：创建任务

Bridge 提供了 HTTP 接口，可以用任何工具创建任务：

```bash
# 用 Python 创建任务
python -c "
import urllib.request, json
data = json.dumps({
    'task_type': 'write_file',
    'payload': {'path': 'allowed_write/demo.txt', 'content': 'Hello from Bridge!', 'overwrite': True}
}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:18080/task',
    data=data,
    headers={'Authorization': 'Bearer alpic-v1-token', 'Content-Type': 'application/json'},
    method='POST'
)
resp = urllib.request.urlopen(req)
print(resp.read().decode())
"
```

Worker 会在下一轮轮询（≤5秒）拉取并执行。

### 查看任务状态

```bash
# 查询任务状态（将 TASK_ID 替换为实际ID）
curl -H "Authorization: Bearer alpic-v1-token" http://127.0.0.1:18080/task/TASK_ID
```

---

## 6. 支持的 task_type 详解

### write_file

写入文件到白名单目录。

**Payload：**
- `path`（必填）：目标路径
- `content`（必填）：文件内容
- `overwrite`（默认 False）：已存在时是否覆盖
- `create_dirs`（默认 False）：是否创建父目录

**安全约束：**
- 路径必须位于 `allowed_dirs` 内
- 不允许 `../` 逃逸到白名单外

### run_python

在子进程执行白名单目录内的 .py 脚本。

**Payload：**
- `script`（必填）：.py 文件路径
- `args`（默认 []）：参数列表（不是 shell 字符串）
- `workdir`（可选）：工作目录
- `timeout_seconds`（可选）：超时秒数

**安全约束：**
- 脚本必须在 `allowed_dirs` 内
- 必须是 `.py` 文件
- `args` 必须是 list，不允许 shell 拼接
- 禁止 `python -c` 任意代码执行

### run_shell_safe

执行白名单内的系统命令。

**Payload：**
- `command`（必填）：命令名（必须在白名单内）
- `args`（默认 []）：参数列表
- `workdir`（可选）：工作目录
- `timeout_seconds`（可选）：超时秒数

**V1 白名单：**
```
python, py
```

**安全约束：**
- 不在白名单的命令一律拒绝
- `shell=False`（始终）
- 不允许命令链、管道、重定向

---

## 7. 安全边界

| 能做 | 不能做 |
|---|---|
| 写白名单目录内的文件 | 写白名单外的文件 |
| 执行白名单目录内的 .py | 执行任意 .py 外的文件 |
| 执行白名单命令（python/py） | 执行任意其他命令 |
| 本地轮询+执行 | 浏览器自动化 |
| 单任务顺序执行 | 多任务并发 |
| 单轮任务 | 自动多轮/自主规划 |
| 简单文件存储 | 数据库 |
| 简单 Bearer Token | 复杂鉴权系统 |

**Worker 不是一个智能 Agent。** 它只被动拉取任务、执行、报告，不负责规划、拆分、自主决策。

---

## 8. 测试说明

### 单元测试（无需启动服务）

```bash
# 存储逻辑
cd alpic-bridge && python test_store.py

# HTTP 接口（需先启动 bridge）
cd alpic-bridge && python test_bridge.py

# Worker 状态和去重
cd alpic-worker && python test_worker.py

# write_file 执行器
cd alpic-worker && python test_write_file.py

# run_python 执行器
cd alpic-worker && python test_run_python.py

# run_shell_safe 执行器
cd alpic-worker && python test_run_shell_safe.py
```

### 集成测试（需同时启动 bridge + worker）

```bash
# write_file 端到端
cd alpic-bridge && python test_integration.py

# run_python 端到端
cd alpic-bridge && python test_run_python_integration.py

# run_shell_safe 端到端
cd alpic-bridge && python test_run_shell_safe_integration.py

# 安全和鉴权测试（需先启动 bridge）
cd alpic-bridge && python test_security.py
```

---

## 9. 已知限制（V1）

- ❌ 浏览器自动化
- ❌ 多任务并发执行
- ❌ 自动多轮任务（自主拆分规划）
- ❌ 大文件传输
- ❌ 复杂鉴权系统
- ❌ 数据库存储
- ❌ 任务优先级/调度
- ❌ 自动重试机制
- ❌ run_shell_safe 除 python/py 外的命令

---

## 10. 快速启动脚本

```bash
# 终端 1：启动 Bridge
cd alpic-bridge && python bridge.py

# 终端 2：启动 Worker
cd alpic-worker && python worker.py

# 终端 3：创建并验证任务
cd alpic-bridge && python test_integration.py
```

---

## 11. 安全加固说明（V1.1）

### 认证机制

所有任务相关接口均需 Bearer Token 认证：

```
Authorization: Bearer <token>
```

**受保护的接口：**
- `GET /task/{task_id}` — 查询任务状态
- `GET /task/next` — Worker 拉取任务
- `POST /task` — 创建任务
- `POST /task/result` — Worker 回传结果

**公开接口（无需认证）：**
- `GET /health` — 健康检查

### Token 配置

**Bridge (alpic-bridge/config.yaml):**
```yaml
bridge:
  token: "CHANGE-ME-IN-PRODUCTION"  # 部署前必须修改
```

**Worker (alpic-worker/config.yaml):**
```yaml
worker:
  token: "CHANGE-ME-IN-PRODUCTION"  # 必须与 bridge 一致
```

### 公网部署注意事项

> **WARNING**: 默认 token `CHANGE-ME-IN-PRODUCTION` 仅适用于本地开发。公网部署前必须修改。

1. **修改 Token**: bridge 和 worker 的 token 必须同时修改为强随机字符串
2. **网络暴露**: 将 bridge 暴露到公网前，确保 token 已修改且足够强
3. **文件存储**: 当前使用本地 JSON 文件存储任务数据，重启后会清空任务队列
4. **数据持久化**: 文件式存储不适合高可靠生产环境，V1.1 仍为最小可用版本
5. **HTTPS**: 当前不支持 HTTPS，公网传输明文 token，建议配合反向代理（nginx/Caddy）使用

### 安全测试

```bash
# 安全和鉴权测试（需先启动 bridge）
cd alpic-bridge && python test_security.py
```

测试覆盖：
- ✅ 带正确 token 能访问受保护接口
- ✅ 不带 token 被 401 拒绝
- ✅ 带错误 token 被 401 拒绝
- ✅ /health 无需认证正常返回

---

## 12. 版本历史

| 版本 | 说明 |
|---|---|
| V1 | 最小可用版本，3种 task_type |
| V1.1 | 安全加固：GET /task/{id} 鉴权、/health 增强、配置路径修复 |

