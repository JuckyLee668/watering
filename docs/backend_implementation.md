# 后端实现说明

## 1. 技术栈

- FastAPI
- SQLAlchemy
- SQLite（默认）
- Uvicorn

## 2. 代码模块

- 微信回调路由：`app/routes/wechat.py`
- 管理路由与页面：`app/routes/admin.py`
- 消息处理服务：`app/services/message_service.py`
- 解析服务：`app/services/llm_service.py`
- 浇水服务：`app/services/watering_service.py`
- 会话日志服务：`app/services/chatlog_service.py`
- 用户状态服务：`app/services/state_service.py`

## 3. 接口清单

### 3.1 微信接口

- `GET /wechat/callback`：公众号验签与在线检查
- `POST /wechat/callback`：接收微信消息并返回被动回复

### 3.2 管理接口

- `GET /api/v1/admin/dashboard`：浇水记录后台
- `GET /api/v1/admin/log`：微信会话日志后台
- `GET /api/v1/records`：记录查询
- `GET /api/v1/records/export`：CSV 导出
- `GET /api/v1/records/{record_id}`：单条记录查询
- `GET /api/v1/chatlogs`：会话日志查询
- `GET /api/v1/statistics`：统计
- `GET /api/v1/health`：健康检查

## 4. 业务逻辑说明

### 4.1 文本上报解析

- 优先本地规则解析（地块、方量、时间）
- 本地规则无法完整解析时调用 LLM
- 无关闲聊返回欢迎引导，不进入记录流程

### 4.2 待确认状态管理

- 创建记录时先落库为 `confirm_status=0`
- 关联 `openid` 保存待确认上下文
- 用户确认后更新为 `confirm_status=1`
- 用户取消后更新为 `confirm_status=2`

### 4.3 幂等与重复消息处理

- 待确认阶段收到同一条文本时：不新建记录，只重发确认提示
- 避免“一次上报出现两条（取消+确认）”

### 4.4 会话日志

- 入站消息、出站消息、错误信息均写入 `wechat_message_logs`
- 后台可按日期、OpenID、方向筛选

## 5. 数据初始化与启动

### 5.1 初始化

```bash
python scripts/init_db.py
```

说明：默认仅建表，不清理历史数据。

### 5.2 强制重建

```bash
python scripts/init_db.py --drop --sample
```

### 5.3 启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 6. 排障建议

- 回调异常先查：`logs/app.log`
- 回调可用性：`python scripts/check_wechat_callback.py`
- 公网诊断：`python scripts/check_public_wechat.py --url https://你的域名/wechat/callback`
