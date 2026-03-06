# 微信智能浇水上报系统

本项目已实现以下能力：

1. **后端代码实现（FastAPI + Redis + MySQL）**
   - 微信回调接口
   - LLM 解析
   - Redis 待确认状态机
   - MySQL 记录入库
2. **微信对接配置**
   - Token 验签
   - 回调地址配置步骤
3. **数据库建表 SQL**
   - MySQL: `scripts/init_database.sql`
   - PostgreSQL: `scripts/init_database_postgresql.sql`
4. **Web 管理后台**
   - 后台页面：`/api/v1/admin/dashboard`
   - 记录查询/统计/CSV 导出
5. **地块信息统一来自 CSV**
   - 示例文件：`data/plots_sample.csv`
   - 地块匹配与初始化均基于该 CSV

## 快速启动

```bash
pip install -r requirements.txt
python scripts/init_db.py --sample
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 文档

- 架构说明：`docs/system_design.md`
- 后端实现：`docs/backend_implementation.md`
- 微信配置：`docs/wechat_integration.md`

