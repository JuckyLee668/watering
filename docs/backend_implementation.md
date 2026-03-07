# 后端实现说明（FastAPI + SQLite）

## 1. 核心模块

- 微信回调入口：`app/routes/wechat.py`
- 消息编排服务：`app/services/message_service.py`
- LLM 解析服务：`app/services/llm_service.py`
- 本地状态机（内存 + TTL）：`app/services/state_service.py`
- 数据库访问：`app/services/watering_service.py`
- 管理接口与后台：`app/routes/admin.py`
- 地块 CSV 目录服务：`app/services/plot_catalog_service.py`

## 2. 端到端流程

1. 微信将用户消息 POST 到 `/wechat/callback`。
2. 服务端校验 `signature/timestamp/nonce`。
3. 解析 XML，提取 `openid + content`。
4. `MessageService` 调用 `LLMService.parse_watering_info` 提取结构化字段。
5. 结果写入本地状态机 `watering:pending:{openid}`，等待用户确认（默认 300 秒）。
6. 用户回复“1/确认”后，`WateringService.create_watering_record` 入库。
7. 用户回复“2/取消”则清除待确认状态。

## 3. 地块 CSV 设计

- 地块主数据文件：`data/plots_sample.csv`
- `PlotCatalogService.sync_to_database()` 按 `plot_code` 同步到 `plots` 表
- 若上报地块不在 CSV 中，系统提示可用标准地块并拒绝入库

## 4. 本地状态键设计

- `watering:pending:{openid}`：待确认数据 JSON
- `user:state:{openid}`：用户状态（`idle` / `waiting_confirm`）

超时由 `config.yaml` 中 `state.pending_timeout` 控制。

## 5. 管理接口

- `GET /api/v1/records`：记录查询（日期/用户/地块/确认状态筛选）
- `GET /api/v1/records/{record_id}`：记录详情
- `GET /api/v1/statistics`：统计查询
- `GET /api/v1/records/export`：CSV 导出
- `GET /api/v1/admin/dashboard`：Web 管理后台

## 6. 启动

```bash
python scripts/init_db.py --sample
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
