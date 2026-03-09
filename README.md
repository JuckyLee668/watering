# 微信智能浇水上报系统

基于 FastAPI + SQLite 的微信公众号浇水上报系统，支持自然语言上报、确认提交流程、后台查询导出、微信会话日志追踪。

## 功能介绍

- [x]微信回调：`GET/POST /wechat/callback`
- [x]地块信息：从 `data/plots_sample.csv` 加载，包含地块名、农户等信息
- [x]数据持久化：SQLite，本地数据库默认是 `data/watering.db`
- [x]记录内容：组长、地块、农户、水量、日期、时间段、时长、原始上报文本、状态、创建时间
- [x]管理后台：`/api/v1/admin/dashboard`，支持按日期、地块名、农户、状态筛选，并导出 CSV
- [x]日志后台：`/api/v1/admin/log`，独立展示微信会话日志
- [X]启动前自检：检查 `.env`、`config.yaml`、地块 CSV、数据库连接、LLM 连通性
- [ ]获取真实用户信息
- [ ]阻止重复提交
## 页面截图

### 管理后台（浇水记录）

![管理后台](docs/images/dashboard.png)

### 条件筛选

![条件筛选](docs/images/select.png)

### 导出示例

![导出示例](docs/images/excelexample.png)

### 微信会话

![微信会话](docs/images/wechat.png)

## 从 0 开始使用

### 1. 环境准备

- Python 3.10+
- Windows PowerShell 或 Linux/macOS Shell
- 公众号服务器配置权限（生产环境需 HTTPS）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置项目

当前配置方式：

- 主要编辑：`.env`
- 配置映射：`config.yaml`
- 示例模板：`.env.example`

配置加载顺序是：先读取项目根目录 `.env`，再解析 `config.yaml` 中的 `${ENV_NAME:-默认值}` 占位。

建议步骤：

1. 复制 `.env.example` 为 `.env`
2. 先准备微信公众号接口信息：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`WECHAT_TOKEN`、`WECHAT_ENCODING_AES_KEY`
3. 再准备大模型配置：`LLM_PROVIDER`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`
4. 按需填写数据库配置
5. 日常只修改 `.env`，不直接改 `config.yaml`

推荐的大模型配置写法是只保留一组通用变量：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=500
```

旧的 `OPENAI_*`、`QWEN_*`、`DEEPSEEK_*`、`ZHIPUAI_*` 变量仍然兼容，但后续建议优先使用上面这组通用变量。

### 4. 准备数据

- 地块数据文件：`data/plots_sample.csv`
- 默认数据库文件：`data/watering.db`

### 5. 先执行自检

```bash
python scripts/self_check.py
```

默认检查项：

- `.env` / `config.yaml` / 地块 CSV 是否存在
- 微信关键配置是否已加载
- 数据库连接是否正常
- 当前 LLM 提供商是否可访问

如果只想跳过大模型检查：

```bash
python scripts/self_check.py --skip-llm
```

### 6. 初始化数据库

```bash
python scripts/init_db.py
```

### 7. 启动服务

直接启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

或使用脚本一键启动。

#### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1
```

常用参数：

- `-SkipInstall`：跳过依赖安装
- `-SkipSelfCheck`：跳过启动前自检
- `-KillPort`：启动前清理占用 `8000` 的进程
- `-Reload`：开发热更新模式
- `-ResetDb`：重建数据库（会清空历史数据）

示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SkipInstall -KillPort
```

#### Linux/macOS

```bash
sh scripts/start_local.sh
```

环境变量：

- `RELOAD=1`：启用热更新
- `SKIP_SELF_CHECK=1`：跳过启动前自检
- `RESET_DB=1`：重建数据库（会清空历史数据）

示例：

```bash
RELOAD=1 sh scripts/start_local.sh
```

### 8. 访问系统

启动后可访问：

- 根路径：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- 回调验活：`http://127.0.0.1:8000/wechat/callback`
- 记录后台：`http://127.0.0.1:8000/api/v1/admin/dashboard`
- 日志后台：`http://127.0.0.1:8000/api/v1/admin/log`

### 9. 配置微信公众号

在公众号后台「开发与接口管理 -> 基本配置 -> 服务器配置」填写：

- URL：`https://你的域名/wechat/callback`
- Token：必须与 `.env` 中的 `WECHAT_TOKEN` 完全一致
- EncodingAESKey：必须与 `.env` 中的 `WECHAT_ENCODING_AES_KEY` 一致

注意：

- 回调地址必须公网可达且 HTTPS 有效
- 正式运行建议关闭 `--reload`
- Token 不一致会报 `verify token fail`

### 10. 了解主要接口

- `GET /api/v1/admin/dashboard`：浇水记录后台页面
- `GET /api/v1/admin/log`：微信会话日志页面
- `GET /api/v1/records`：记录查询
- `GET /api/v1/records/export`：CSV 导出
- `GET /api/v1/chatlogs`：微信会话日志查询
- `GET /api/v1/statistics`：统计
- `GET /api/v1/health`：健康检查

## 常见问题

### 1. `/wechat/callback` 访问失败

先本机检查：

```bash
python scripts/check_wechat_callback.py
```

再做公网检查：

```bash
python scripts/check_public_wechat.py --url https://你的域名/wechat/callback
```

### 2. 微信发消息无回复

按顺序排查：

1. 公众号后台 URL / Token / 加密模式是否一致
2. 域名 DNS、TLS、隧道或反向代理是否正常
3. 服务是否稳定运行，避免频繁重启
4. 查看 `logs/app.log` 和 `/api/v1/admin/log`

### 3. 启动报端口占用（WinError 10048）

一般是之前的实例没有正常退出，或者其他程序占用了 `8000` 端口。可直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SkipInstall -KillPort
```

如果仍想手动处理：

1. 结束占用 `8000` 的进程
2. 或修改 `.env` 里的 `APP_PORT`

### 4. 自检失败

优先检查：

1. `.env` 是否存在，关键字段是否为空
2. `config.yaml` 是否还保留 `${ENV_NAME:-默认值}` 占位
3. `data/plots_sample.csv` 是否存在
4. 大模型 API Key、Base URL、模型名是否填写正确

如果只是临时跳过大模型检查：

```bash
python scripts/self_check.py --skip-llm
```

### 5. 一次上报出现两条记录

已优化：待确认阶段若收到同一条重复文本，仅重发确认提示，不会重复建记录。

## 安全建议

- 不要把真实 `.env` 提交到仓库
- 不要把真实 `app_secret`、`api_key` 写回 `config.yaml`
- 通过 `.env` 注入敏感信息
- 生产环境启用 HTTPS、访问控制和备份策略

## 目录结构

- `app/`：后端代码
- `data/`：SQLite 数据库与示例 CSV
- `scripts/`：初始化、启动、自检脚本
- `docs/`：系统设计与对接文档
- `logs/`：运行日志（`logs/app.log`）

## 相关文档

- `docs/system_design.md`
- `docs/backend_implementation.md`
- `docs/wechat_integration.md`
