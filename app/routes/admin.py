# -*- coding: utf-8 -*-
"""
管理接口路由
Admin API Routes

提供浇水记录查询、统计等管理功能
"""

from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
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
    """
    获取浇水记录列表

    支持多条件筛选
    """
    watering_service = get_watering_service(db)

    # 解析日期
    start = None
    end = None

    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

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


@router.get("/records/{record_id}", response_model=WateringRecordResponse)
async def get_record(
    record_id: int,
    db: Session = Depends(get_db),
):
    """
    获取单条浇水记录详情
    """
    watering_service = get_watering_service(db)
    record = watering_service.get_record_by_id(record_id)

    if not record:
        from fastapi import HTTPException
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
    """
    获取浇水统计信息
    """
    watering_service = get_watering_service(db)

    # 解析日期，默认今天
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start = datetime.now().date()

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end = start

    stats = watering_service.get_statistics(
        start_date=start,
        end_date=end,
        user_id=user_id,
        plot_id=plot_id,
    )

    return stats


@router.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }
