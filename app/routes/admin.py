import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.models.database import get_db
from app.services.chatlog_service import get_chatlog_service
from app.services.watering_service import get_watering_service


router = APIRouter(prefix="/api/v1", tags=["admin"], dependencies=[Depends(require_admin_token)])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


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
async def admin_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/dashboard.html")


@router.get("/admin/log", response_class=HTMLResponse)
async def admin_log_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/log.html")


@router.get("/records", response_model=List[WateringRecordResponse])
async def get_records(
    start_date: Optional[str] = Query(None, description="start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="end date YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="leader id"),
    plot_id: Optional[int] = Query(None, description="plot id"),
    plot_name: Optional[str] = Query(None, description="plot name"),
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
        plot_name=plot_name,
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
    plot_name: Optional[str] = Query(None, description="plot name"),
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
        plot_name=plot_name,
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
