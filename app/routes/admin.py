from datetime import datetime
from io import StringIO
from typing import List, Optional
import csv

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.chatlog_service import get_chatlog_service
from app.services.watering_service import get_watering_service


router = APIRouter(prefix="/api/v1", tags=["admin"])


class WateringRecordResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    leader_name: Optional[str] = None
    leader_openid: Optional[str] = None
    plot_id: Optional[int] = None
    plot_name: Optional[str] = None
    plot_owner_name: Optional[str] = None
    volume: float
    operation_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    raw_input: Optional[str] = None
    confirm_status: int
    create_time: str

    model_config = ConfigDict(from_attributes=True)


class StatisticsResponse(BaseModel):
    total_count: int
    total_volume: float
    avg_volume: float
    avg_duration: float
    start_date: str
    end_date: str


class ChatLogResponse(BaseModel):
    id: int
    openid: Optional[str] = None
    msg_type: str
    direction: str
    content: Optional[str] = None
    status: str
    error: Optional[str] = None
    create_time: str

    model_config = ConfigDict(from_attributes=True)


def _parse_date(date_str: Optional[str]):
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard() -> HTMLResponse:
    html = """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>浇水记录管理后台</title>
  <style>
    body { font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; margin: 0; background: #f5f7f6; }
    .wrap { max-width: 1280px; margin: 20px auto; padding: 0 16px; }
    .card { background: #fff; border: 1px solid #dfe5e2; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .row { display: grid; grid-template-columns: repeat(7, minmax(120px, 1fr)); gap: 10px; align-items: end; }
    label { display:block; font-size: 12px; color: #5c6861; margin-bottom: 4px; }
    input, select, button { width: 100%; height: 36px; border: 1px solid #d6ded9; border-radius: 8px; padding: 0 10px; }
    button { background: #2f7a56; color: #fff; cursor: pointer; }
    .secondary { background: #fff; color: #243129; }
    table { width: 100%; min-width: 1220px; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #e5ece8; padding: 10px; text-align: left; font-size: 13px; }
    th { background: #f3f8f5; }
    .ok { color: #157347; }
    .pending { color: #bd7a00; }
    .cancel { color: #b3261e; }
  </style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"card\">
    <h2 style=\"margin:0 0 10px;\">浇水记录管理后台</h2>
    <div style=\"margin:0 0 10px;\"><a href=\"/api/v1/admin/log\" style=\"color:#2f7a56;text-decoration:none;\">打开微信会话日志独立页面</a></div>
    <div class=\"row\">
      <div><label>开始日期</label><input type=\"date\" id=\"start_date\" /></div>
      <div><label>结束日期</label><input type=\"date\" id=\"end_date\" /></div>
      <div>
        <label>确认状态</label>
        <select id=\"confirm_status\">
          <option value=\"\">全部</option>
          <option value=\"1\">已确认</option>
          <option value=\"0\">待确认</option>
          <option value=\"2\">已取消</option>
        </select>
      </div>
      <div>
        <label>每页数量</label>
        <select id=\"limit\"><option>50</option><option selected>100</option><option>200</option></select>
      </div>
      <div><label>农户</label><input type=\"text\" id=\"owner_name\" placeholder=\"按所有者筛选\" /></div>
      <div><button onclick=\"loadData()\">查询</button></div>
      <div><button class=\"secondary\" onclick=\"exportCsv()\">导出 CSV</button></div>
    </div>
    <div id=\"meta\" style=\"margin-top:8px;color:#5c6861;font-size:12px;\"></div>
  </div>

  <div class=\"card\" style=\"overflow:auto;\">
    <table>
      <thead>
        <tr>
          <th>ID</th><th>组长</th><th>地块</th><th>农户</th><th>水量(方)</th><th>日期</th><th>时间段</th><th>时长</th><th>原始上报</th><th>状态</th><th>创建时间</th>
        </tr>
      </thead>
      <tbody id=\"tbody\"></tbody>
    </table>
  </div>

</div>
<script>
function today(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
function getFilters(){const p=new URLSearchParams();const sd=document.getElementById('start_date').value;const ed=document.getElementById('end_date').value;const cs=document.getElementById('confirm_status').value;const l=document.getElementById('limit').value;const owner=document.getElementById('owner_name').value;if(sd)p.set('start_date',sd);if(ed)p.set('end_date',ed);if(cs!=='')p.set('confirm_status',cs);if(l)p.set('limit',l);if(owner)p.set('owner_name',owner);p.set('offset','0');return p;}
function statusText(s){if(s===1)return '<span class="ok">已确认</span>';if(s===0)return '<span class="pending">待确认</span>';if(s===2)return '<span class="cancel">已取消</span>';return s;}
function esc(t){return String(t||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}
function renderRows(rows){const tb=document.getElementById('tbody');tb.innerHTML='';if(!rows.length){tb.innerHTML='<tr><td colspan="11">无记录</td></tr>';return;}rows.forEach(r=>{const tr=document.createElement('tr');const trange=`${r.start_time||'-'} ~ ${r.end_time||'-'}`;tr.innerHTML=`<td>${r.id}</td><td>${r.leader_name||r.user_name||r.user_id}</td><td>${r.plot_name||'-'}</td><td>${r.plot_owner_name||'-'}</td><td>${Number(r.volume||0).toFixed(1)}</td><td>${r.operation_date||'-'}</td><td>${trange}</td><td>${r.duration_minutes??'-'}</td><td title="${esc(r.raw_input)}">${esc(r.raw_input)||'-'}</td><td>${statusText(r.confirm_status)}</td><td>${r.create_time||'-'}</td>`;tb.appendChild(tr);});}
async function loadData(){const p=getFilters();document.getElementById('meta').innerText='加载中...';const res=await fetch('/api/v1/records?'+p.toString());if(!res.ok){document.getElementById('meta').innerText='加载失败';return;}const rows=await res.json();renderRows(rows);document.getElementById('meta').innerText=`已加载 ${rows.length} 条`;}
function exportCsv(){const p=getFilters();window.open('/api/v1/records/export?'+p.toString(),'_blank');}
(function(){const t=today();document.getElementById('start_date').value=t;document.getElementById('end_date').value=t;loadData();})();
</script>
</body>
</html>
"""
    return HTMLResponse(content=html)


def _build_admin_log_html() -> str:
    return """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>微信会话日志</title>
  <style>
    body { font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; margin: 0; background: #f5f7f6; }
    .wrap { max-width: 1280px; margin: 20px auto; padding: 0 16px; }
    .card { background: #fff; border: 1px solid #dfe5e2; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .row { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; align-items: end; }
    label { display:block; font-size: 12px; color: #5c6861; margin-bottom: 4px; }
    input, select, button { width: 100%; height: 36px; border: 1px solid #d6ded9; border-radius: 8px; padding: 0 10px; }
    button { background: #2f7a56; color: #fff; cursor: pointer; }
    table { width: 100%; min-width: 1080px; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #e5ece8; padding: 10px; text-align: left; font-size: 13px; }
    th { background: #f3f8f5; }
  </style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"card\">
    <h2 style=\"margin:0 0 10px;\">微信会话日志</h2>
    <div style=\"margin:0 0 10px;\"><a href=\"/api/v1/admin/dashboard\" style=\"color:#2f7a56;text-decoration:none;\">返回管理后台</a></div>
    <div class=\"row\">
      <div><label>开始日期</label><input type=\"date\" id=\"start_date\" /></div>
      <div><label>结束日期</label><input type=\"date\" id=\"end_date\" /></div>
      <div><label>组长OpenID</label><input type=\"text\" id=\"openid\" placeholder=\"按组长 openid 精确筛选\" /></div>
      <div>
        <label>方向</label>
        <select id=\"direction\">
          <option value=\"\">全部</option>
          <option value=\"in\">入站</option>
          <option value=\"out\">出站</option>
        </select>
      </div>
      <div><label>每页数量</label><select id=\"limit\"><option>50</option><option selected>100</option><option>200</option></select></div>
      <div><button onclick=\"loadLogs()\">查询日志</button></div>
    </div>
    <div id=\"meta\" style=\"margin-top:8px;color:#5c6861;font-size:12px;\"></div>
  </div>

  <div class=\"card\" style=\"overflow:auto;\">
    <table>
      <thead>
        <tr>
          <th>ID</th><th>时间</th><th>组长OpenID</th><th>方向</th><th>类型</th><th>状态</th><th>内容</th><th>错误</th>
        </tr>
      </thead>
      <tbody id=\"tbody\"></tbody>
    </table>
  </div>
</div>
<script>
function today(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
function esc(t){return String(t||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}
function getFilters(){const p=new URLSearchParams();const sd=document.getElementById('start_date').value;const ed=document.getElementById('end_date').value;const oid=document.getElementById('openid').value;const dir=document.getElementById('direction').value;const limit=document.getElementById('limit').value;if(sd)p.set('start_date',sd);if(ed)p.set('end_date',ed);if(oid)p.set('openid',oid);if(dir)p.set('direction',dir);if(limit)p.set('limit',limit);p.set('offset','0');return p;}
function renderRows(rows){const tb=document.getElementById('tbody');tb.innerHTML='';if(!rows.length){tb.innerHTML='<tr><td colspan=\"8\">无日志</td></tr>';return;}rows.forEach(r=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${r.id}</td><td>${r.create_time||'-'}</td><td>${r.openid||'-'}</td><td>${r.direction||'-'}</td><td>${r.msg_type||'-'}</td><td>${r.status||'-'}</td><td title=\"${esc(r.content)}\">${esc(r.content)||'-'}</td><td title=\"${esc(r.error)}\">${esc(r.error)||'-'}</td>`;tb.appendChild(tr);});}
async function loadLogs(){const p=getFilters();document.getElementById('meta').innerText='加载中...';const res=await fetch('/api/v1/chatlogs?'+p.toString());if(!res.ok){document.getElementById('meta').innerText='日志加载失败';return;}const rows=await res.json();renderRows(rows);document.getElementById('meta').innerText=`已加载 ${rows.length} 条`;}
(function(){const t=today();document.getElementById('start_date').value=t;document.getElementById('end_date').value=t;loadLogs();})();
</script>
</body>
</html>"""


@router.get("/admin/log", response_class=HTMLResponse)
async def admin_log_page() -> HTMLResponse:
    return HTMLResponse(content=_build_admin_log_html())


@router.get("/records", response_model=List[WateringRecordResponse])
async def get_records(
    start_date: Optional[str] = Query(None, description="start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="end date YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="leader id"),
    plot_id: Optional[int] = Query(None, description="plot id"),
    owner_name: Optional[str] = Query(None, description="plot owner name"),
    confirm_status: Optional[int] = Query(None, description="confirm status"),
    limit: int = Query(100, ge=1, le=1000, description="limit"),
    offset: int = Query(0, ge=0, description="offset"),
    db: Session = Depends(get_db),
):
    watering_service = get_watering_service(db)
    records = watering_service.get_all_records(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        user_id=user_id,
        plot_id=plot_id,
        owner_name=owner_name,
        confirm_status=confirm_status,
        limit=limit,
        offset=offset,
    )
    return [record.to_dict() for record in records]


@router.get("/records/export")
async def export_records_csv(
    start_date: Optional[str] = Query(None, description="start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="end date YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="leader id"),
    plot_id: Optional[int] = Query(None, description="plot id"),
    owner_name: Optional[str] = Query(None, description="plot owner name"),
    confirm_status: Optional[int] = Query(None, description="confirm status"),
    db: Session = Depends(get_db),
):
    watering_service = get_watering_service(db)
    records = watering_service.get_all_records(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        user_id=user_id,
        plot_id=plot_id,
        owner_name=owner_name,
        confirm_status=confirm_status,
        limit=5000,
        offset=0,
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "记录ID",
        "组长ID",
        "组长昵称",
        "地块ID",
        "地块名称",
        "农户",
        "浇水方数",
        "作业日期",
        "开始时间",
        "结束时间",
        "时长(分钟)",
        "原始上报",
        "确认状态",
        "创建时间",
    ])

    status_map = {0: "待确认", 1: "已确认", 2: "已取消"}

    for record in records:
        row = record.to_dict()
        writer.writerow([
            row.get("id"),
            row.get("user_id"),
            row.get("leader_name") or row.get("user_name") or "",
            row.get("plot_id") or "",
            row.get("plot_name") or "",
            row.get("plot_owner_name") or "",
            row.get("volume") or 0,
            row.get("operation_date") or "",
            row.get("start_time") or "",
            row.get("end_time") or "",
            row.get("duration_minutes") or "",
            row.get("raw_input") or "",
            status_map.get(row.get("confirm_status"), row.get("confirm_status")),
            row.get("create_time") or "",
        ])

    output.seek(0)
    csv_content = "\ufeff" + output.getvalue()
    filename = f"watering_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/records/{record_id}", response_model=WateringRecordResponse)
async def get_record(record_id: int, db: Session = Depends(get_db)):
    watering_service = get_watering_service(db)
    record = watering_service.get_record_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="record not found")
    return record.to_dict()


@router.get("/chatlogs", response_model=List[ChatLogResponse])
async def get_chatlogs(
    start_date: Optional[str] = Query(None, description="start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="end date YYYY-MM-DD"),
    openid: Optional[str] = Query(None, description="leader wechat openid"),
    direction: Optional[str] = Query(None, description="in/out"),
    limit: int = Query(100, ge=1, le=1000, description="limit"),
    offset: int = Query(0, ge=0, description="offset"),
    db: Session = Depends(get_db),
):
    service = get_chatlog_service(db)
    logs = service.get_logs(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        openid=openid,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    return [x.to_dict() for x in logs]


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    start_date: Optional[str] = Query(None, description="start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="end date YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="leader id"),
    plot_id: Optional[int] = Query(None, description="plot id"),
    db: Session = Depends(get_db),
):
    watering_service = get_watering_service(db)
    start = _parse_date(start_date) or datetime.now().date()
    end = _parse_date(end_date) or start
    return watering_service.get_statistics(
        start_date=start,
        end_date=end,
        user_id=user_id,
        plot_id=plot_id,
    )


@router.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

