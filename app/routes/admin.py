# -*- coding: utf-8 -*-
"""
管理接口路由
Admin API Routes

提供浇水记录查询、统计、导出和简易后台页面功能
"""

from datetime import datetime
from io import StringIO
from typing import Optional, List
import csv

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.watering_service import get_watering_service


# 创建路由
router = APIRouter(prefix="/api/v1", tags=["管理接口"])


# ============================================================
# 数据模型
# ============================================================


class WateringRecordResponse(BaseModel):
    """浇水记录响应"""

    id: int
    user_id: int
    user_name: Optional[str] = None
    plot_id: Optional[int] = None
    plot_name: Optional[str] = None
    volume: float
    operation_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    confirm_status: int
    create_time: str

    class Config:
        from_attributes = True


class StatisticsResponse(BaseModel):
    """统计信息响应"""

    total_count: int
    total_volume: float
    avg_volume: float
    avg_duration: float
    start_date: str
    end_date: str


# ============================================================
# 管理后台页面
# ============================================================


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """简易Web管理后台（查看/筛选/导出）"""
    html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>浇水记录管理后台</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
    input, select, button { padding: 8px 10px; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { border: 1px solid #ddd; padding: 8px; font-size: 14px; }
    th { background: #f7f7f7; }
    .stat { background: #fafafa; border: 1px solid #eee; padding: 12px; margin: 8px 0; }
  </style>
</head>
<body>
  <h2>📋 浇水记录管理后台</h2>
  <div class="row">
    <label>开始日期 <input type="date" id="start_date"/></label>
    <label>结束日期 <input type="date" id="end_date"/></label>
    <label>确认状态
      <select id="confirm_status">
        <option value="">全部</option>
        <option value="1">已确认</option>
        <option value="0">待确认</option>
      </select>
    </label>
    <button onclick="loadData()">查询</button>
    <button onclick="exportCsv()">导出CSV</button>
  </div>

  <div id="stats" class="stat">统计信息加载中...</div>

  <table>
    <thead>
      <tr>
        <th>ID</th><th>用户</th><th>地块</th><th>方数</th><th>日期</th><th>时间</th><th>时长(分钟)</th><th>状态</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

<script>
function filters() {
  const start_date = document.getElementById('start_date').value;
  const end_date = document.getElementById('end_date').value;
  const confirm_status = document.getElementById('confirm_status').value;
  const p = new URLSearchParams();
  if (start_date) p.set('start_date', start_date);
  if (end_date) p.set('end_date', end_date);
  if (confirm_status !== '') p.set('confirm_status', confirm_status);
  return p;
}

async function loadData() {
  const p = filters();
  const [recordsRes, statsRes] = await Promise.all([
    fetch('/api/v1/records?' + p.toString()),
    fetch('/api/v1/statistics?' + p.toString())
  ]);
  const records = await recordsRes.json();
  const stats = await statsRes.json();

  document.getElementById('stats').innerText =
    `统计：共 ${stats.total_count} 条，合计 ${stats.total_volume} 方，平均 ${stats.avg_volume} 方，平均时长 ${stats.avg_duration.toFixed(1)} 分钟`;

  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  records.forEach(r => {
    const tr = document.createElement('tr');
    const timeText = `${r.start_time || '-'} ~ ${r.end_time || '-'}`;
    tr.innerHTML = `<td>${r.id}</td><td>${r.user_name || r.user_id}</td><td>${r.plot_name || '-'}</td><td>${r.volume}</td><td>${r.operation_date}</td><td>${timeText}</td><td>${r.duration_minutes || '-'}</td><td>${r.confirm_status === 1 ? '已确认' : '待确认'}</td>`;
    tbody.appendChild(tr);
  });
}

function exportCsv() {
  const p = filters();
  window.open('/api/v1/records/export?' + p.toString(), '_blank');
}

loadData();
</script>
</body>
</html>
"""
    return HTMLResponse(content=html)


# ============================================================
# 查询接口
# ============================================================


@router.get("/records", response_model=List[WateringRecordResponse])
async def get_records(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    plot_id: Optional[int] = Query(None, description="地块ID"),
    confirm_status: Optional[int] = Query(None, description="确认状态"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
):
    """获取浇水记录列表（支持多条件筛选）"""
    watering_service = get_watering_service(db)

    start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

    records = watering_service.get_all_records(
        start_date=start,
        end_date=end,
        user_id=user_id,
        plot_id=plot_id,
        confirm_status=confirm_status,
        limit=limit,
        offset=offset,
    )

    return [record.to_dict() for record in records]


@router.get("/records/export")
async def export_records_csv(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    plot_id: Optional[int] = Query(None, description="地块ID"),
    confirm_status: Optional[int] = Query(None, description="确认状态"),
    db: Session = Depends(get_db),
):
    """导出浇水记录CSV"""
    watering_service = get_watering_service(db)

    start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

    records = watering_service.get_all_records(
        start_date=start,
        end_date=end,
        user_id=user_id,
        plot_id=plot_id,
        confirm_status=confirm_status,
        limit=5000,
        offset=0,
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "记录ID",
        "用户ID",
        "用户姓名",
        "地块ID",
        "地块名称",
        "浇水方数",
        "作业日期",
        "开始时间",
        "结束时间",
        "时长(分钟)",
        "确认状态",
        "创建时间",
    ])

    for record in records:
        row = record.to_dict()
        writer.writerow([
            row.get("id"),
            row.get("user_id"),
            row.get("user_name") or "",
            row.get("plot_id") or "",
            row.get("plot_name") or "",
            row.get("volume") or 0,
            row.get("operation_date") or "",
            row.get("start_time") or "",
            row.get("end_time") or "",
            row.get("duration_minutes") or "",
            "已确认" if row.get("confirm_status") == 1 else "待确认",
            row.get("create_time") or "",
        ])

    output.seek(0)
    filename = f"watering_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/records/{record_id}", response_model=WateringRecordResponse)
async def get_record(
    record_id: int,
    db: Session = Depends(get_db),
):
    """获取单条浇水记录详情"""
    watering_service = get_watering_service(db)
    record = watering_service.get_record_by_id(record_id)

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    return record.to_dict()


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    plot_id: Optional[int] = Query(None, description="地块ID"),
    db: Session = Depends(get_db),
):
    """获取浇水统计信息"""
    watering_service = get_watering_service(db)

    start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else datetime.now().date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else start

    stats = watering_service.get_statistics(
        start_date=start,
        end_date=end,
        user_id=user_id,
        plot_id=plot_id,
    )

    return stats


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }
