# 微信智能浇水上报系统

基于 FastAPI + SQLite 的微信公众号浇水上报系统，支持消息解析、确认提交流程、管理后台查询导出、会话日志追踪。

## 功能概览

- 微信回调：`GET/POST /wechat/callback`
- 上报解析：优先本地规则解析，必要时调用大模型（OpenAI / 智谱 / 通义 / DeepSeek）
- 确认流程：用户回复 `1/确认` 提交，`2/取消` 放弃
- 状态持久化：使用 SQLite（不依赖 Redis）
- 管理后台：记录查询、按农户筛选、CSV 导出
- 日志面板：微信入站/出站消息与错误可视化

## 目录结构

- `app/`：后端代码
- `data/`：SQLite 数据库与示例 CSV
- `scripts/`：初始化、启动、自检脚本
- `docs/`：系统设计和对接文档
- `logs/`：运行日志（`logs/app.log`）

## 环境要求

- Python 3.10+
- Windows PowerShell 或 Linux/macOS Shell
- 公众号已配置服务器地址（生产需 HTTPS）

## 快速启动

```bash
pip install -r requirements.txt
python scripts/init_db.py --drop --sample
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后可访问：

- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- 回调验活：`http://127.0.0.1:8000/wechat/callback`
- 管理后台：`http://127.0.0.1:8000/api/v1/admin/dashboard`

## 一键初始化 + 启动

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1
```

常用参数：

- `-SkipInstall`：跳过依赖安装
- `-Reload`：开发热更新模式
- `-KillPort`：启动前清理占用 `8000` 端口的进程

示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SkipInstall -KillPort
```

### Linux/macOS

```bash
sh scripts/start_local.sh
```

开启热更新：

```bash
RELOAD=1 sh scripts/start_local.sh
```

## 微信公众号配置

在公众号后台「开发与接口管理 -> 基本配置 -> 服务器配置」填写：

- URL：`https://你的域名/wechat/callback`
- Token：与 `config.yaml -> wechat.token` 完全一致
- EncodingAESKey：与配置一致（或先用明文模式）
- 消息加解密方式：建议先用明文模式完成联调

注意：

- 回调地址必须公网可达且 HTTPS 可用
- 稳定运行建议关闭 `--reload`
- Token 不一致会报 `verify token fail`

## 管理接口

- 后台页面：`GET /api/v1/admin/dashboard`
- 记录查询：`GET /api/v1/records`
- 记录导出：`GET /api/v1/records/export`
- 会话日志：`GET /api/v1/chatlogs`
- 统计：`GET /api/v1/statistics`
- 健康检查：`GET /api/v1/health`

## 常见问题排查

### 1) `/wechat/callback` 无法访问

先本机检查：

```bash
python scripts/check_wechat_callback.py
```

公网检查：

```bash
python scripts/check_public_wechat.py --url https://你的域名/wechat/callback
```

### 2) 微信发消息无回复

按顺序检查：

1. 公众号后台 URL/Token/加密模式是否与服务一致
2. 域名是否公网可达（DNS、TLS 证书、反代/隧道）
3. 服务是否稳定运行（避免 `--reload` 频繁重启）
4. 查看 `logs/app.log` 与后台「微信会话日志」是否有入站记录

### 3) 启动报端口占用（WinError 10048）

使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SkipInstall -KillPort
```

### 4) 一次上报出现两条记录

系统已优化：待确认阶段如果重复收到同一条文本，只重发确认提示，不再新建记录。

## 配置说明

核心配置文件：`config.yaml`

关键项：

- `wechat.app_id / wechat.app_secret / wechat.token`
- `llm.provider`（`openai` / `zhipuai` / `qwen` / `deepseek`）
- `database.sqlite_path`
- `plots.csv_path`

## 安全建议

- 不要把真实 `app_secret`、`api_key` 提交到代码仓库
- 生产环境建议通过环境变量或私有配置覆盖敏感字段
- 对外服务建议启用 HTTPS 与访问控制

## 相关文档

- `docs/system_design.md`
- `docs/backend_implementation.md`
- `docs/wechat_integration.md`
