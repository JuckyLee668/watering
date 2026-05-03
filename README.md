# 微信智能浇水上报系统

基于 FastAPI + SQLAlchemy 的微信公众号浇水上报系统，支持自然语言上报、确认提交、后台查询、CSV 导出和微信会话日志追踪。

## 功能

- 微信回调：`GET/POST /wechat/callback`
- 自然语言解析：优先本地规则，必要时调用大模型
- 记录持久化：默认 SQLite，也支持 MySQL/PostgreSQL 风格连接串
- 待确认状态：用户提交后先生成待确认记录，回复 `1` 确认、`2` 取消
- 后台管理：`/api/v1/admin/dashboard`
- 会话日志：`/api/v1/admin/log`
- CSV 导出：`/api/v1/records/export`
- 启动前自检：`python scripts/self_check.py`

## 快速开始

```bash
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows 本地启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SkipInstall -KillPort
```

## 配置

复制 `.env.example` 为 `.env`，至少配置：

```env
WECHAT_APP_ID=your_app_id
WECHAT_APP_SECRET=your_app_secret
WECHAT_TOKEN=your_wechat_token
WECHAT_ENCODING_AES_KEY=your_encoding_aes_key

LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

生产环境建议额外配置：

```env
APP_DEBUG=false
ADMIN_TOKEN=change-me
CORS_ALLOW_ORIGINS=https://your-admin-domain.example
CORS_ALLOW_CREDENTIALS=true
```

配置加载顺序：先读取 `.env`，再解析 `config.yaml` 中的 `${ENV_NAME:-default}` 占位符。

## 接口

- `GET /`：服务状态
- `GET /api/v1/health`：健康检查
- `GET /wechat/callback`：微信服务器校验
- `POST /wechat/callback`：微信消息回调
- `GET /api/v1/admin/dashboard`：浇水记录后台
- `GET /api/v1/admin/log`：微信会话日志
- `GET /api/v1/records`：记录查询
- `GET /api/v1/records/export`：记录 CSV 导出
- `GET /api/v1/chatlogs`：会话日志查询
- `GET /api/v1/statistics`：统计数据

当 `ADMIN_TOKEN` 非空时，所有 `/api/v1/*` 后台接口都需要请求头：

```http
X-Admin-Token: change-me
```

## 测试

```bash
python -m compileall app tests scripts
pytest
```

CI 配置位于 `.github/workflows/ci.yml`。

## 部署

Docker：

```bash
docker build -t watering .
docker run --env-file .env -p 8000:8000 watering
```

生产建议：

- 使用 HTTPS 暴露微信回调地址
- 配置 `ADMIN_TOKEN`
- 禁止将真实 `.env` 提交到仓库
- 关闭 `APP_DEBUG`
- 使用明确的 `CORS_ALLOW_ORIGINS`
- 定期备份数据库

## 目录结构

- `app/routes/`：FastAPI 路由
- `app/services/`：业务服务
- `app/models/`：SQLAlchemy 模型和数据库连接
- `app/schemas/`：结构化输入输出模型
- `app/templates/`：后台 HTML 模板
- `app/wechat/`：微信签名和消息工具
- `data/`：示例地块 CSV 与本地数据库
- `scripts/`：初始化、自检、启动脚本
- `tests/`：自动化测试
