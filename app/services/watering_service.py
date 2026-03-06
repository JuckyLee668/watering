# -*- coding: utf-8 -*-
"""
浇水记录服务
Watering Record Service

负责浇水记录的数据库操作
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.database import User, Plot, WateringRecord
from app.core.exceptions import (
    DatabaseException,
    UserNotFoundException,
    PlotNotFoundException,
)


class WateringService:
    """浇水记录服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_user(self, openid: str, name: str = None) -> User:
        """
        获取或创建用户

        Args:
            openid: 微信OpenID
            name: 用户姓名

        Returns:
            User实例
        """
        user = self.db.query(User).filter(User.openid == openid).first()

        if user is None:
            # 创建新用户
            user = User(
                openid=openid,
                name=name or "未知用户",
                status=1,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        return user

    def get_or_create_plot(self, plot_name: str) -> Optional[Plot]:
        """
        获取或创建地块

        Args:
            plot_name: 地块名称

        Returns:
            Plot实例，如果不存在则返回None
        """
        # 先尝试精确匹配
        plot = self.db.query(Plot).filter(Plot.plot_name == plot_name).first()
        if plot:
            return plot

        # 尝试模糊匹配
        plot = self.db.query(Plot).filter(
            Plot.plot_name.like(f"%{plot_name}%")
        ).first()

        return plot

    def create_watering_record(
        self,
        user_id: int,
        plot_id: Optional[int],
        plot_name: str,
        volume: float,
        operation_date: date,
        start_time: Optional[time],
        end_time: Optional[time],
        raw_input: str,
        confirm_status: int = 1,
    ) -> WateringRecord:
        """
        创建浇水记录

        Args:
            user_id: 用户ID
            plot_id: 地块ID
            plot_name: 地块名称
            volume: 浇水方数
            operation_date: 作业日期
            start_time: 开始时间
            end_time: 结束时间
            raw_input: 原始输入
            confirm_status: 确认状态

        Returns:
            WateringRecord实例
        """
        # 计算时长
        duration_minutes = None
        if start_time and end_time:
            start_dt = datetime.combine(date.today(), start_time)
            end_dt = datetime.combine(date.today(), end_time)
            if end_dt < start_dt:
                # 跨天情况
                end_dt += timedelta(days=1)
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)

        # 创建记录
        record = WateringRecord(
            user_id=user_id,
            plot_id=plot_id,
            volume=volume,
            operation_date=operation_date,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            raw_input=raw_input,
            confirm_status=confirm_status,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        return record

    def get_user_records(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[WateringRecord]:
        """
        获取用户的浇水记录

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制

        Returns:
            浇水记录列表
        """
        query = self.db.query(WateringRecord).filter(
            WateringRecord.user_id == user_id
        )

        if start_date:
            query = query.filter(WateringRecord.operation_date >= start_date)
        if end_date:
            query = query.filter(WateringRecord.operation_date <= end_date)

        return query.order_by(
            desc(WateringRecord.operation_date),
            desc(WateringRecord.create_time),
        ).limit(limit).all()

    def get_plot_records(
        self,
        plot_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[WateringRecord]:
        """
        获取地块的浇水记录

        Args:
            plot_id: 地块ID
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制

        Returns:
            浇水记录列表
        """
        query = self.db.query(WateringRecord).filter(
            WateringRecord.plot_id == plot_id
        )

        if start_date:
            query = query.filter(WateringRecord.operation_date >= start_date)
        if end_date:
            query = query.filter(WateringRecord.operation_date <= end_date)

        return query.order_by(
            desc(WateringRecord.operation_date),
            desc(WateringRecord.create_time),
        ).limit(limit).all()

    def get_all_records(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[int] = None,
        plot_id: Optional[int] = None,
        confirm_status: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WateringRecord]:
        """
        获取所有浇水记录（支持筛选）

        Args:
            start_date: 开始日期
            end_date: 结束日期
            user_id: 用户ID筛选
            plot_id: 地块ID筛选
            confirm_status: 确认状态筛选
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            浇水记录列表
        """
        query = self.db.query(WateringRecord)

        if start_date:
            query = query.filter(WateringRecord.operation_date >= start_date)
        if end_date:
            query = query.filter(WateringRecord.operation_date <= end_date)
        if user_id:
            query = query.filter(WateringRecord.user_id == user_id)
        if plot_id:
            query = query.filter(WateringRecord.plot_id == plot_id)
        if confirm_status is not None:
            query = query.filter(WateringRecord.confirm_status == confirm_status)

        return query.order_by(
            desc(WateringRecord.operation_date),
            desc(WateringRecord.create_time),
        ).offset(offset).limit(limit).all()

    def get_record_by_id(self, record_id: int) -> Optional[WateringRecord]:
        """
        根据ID获取浇水记录

        Args:
            record_id: 记录ID

        Returns:
            WateringRecord实例
        """
        return self.db.query(WateringRecord).filter(
            WateringRecord.id == record_id
        ).first()

    def get_statistics(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[int] = None,
        plot_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        获取浇水统计信息

        Args:
            start_date: 开始日期
            end_date: 结束日期
            user_id: 用户ID（可选）
            plot_id: 地块ID（可选）

        Returns:
            统计信息字典
        """
        from sqlalchemy import func

        query = self.db.query(
            func.count(WateringRecord.id).label("total_count"),
            func.sum(WateringRecord.volume).label("total_volume"),
            func.avg(WateringRecord.volume).label("avg_volume"),
            func.avg(WateringRecord.duration_minutes).label("avg_duration"),
        ).filter(
            WateringRecord.operation_date >= start_date,
            WateringRecord.operation_date <= end_date,
            WateringRecord.confirm_status == 1,
        )

        if user_id:
            query = query.filter(WateringRecord.user_id == user_id)
        if plot_id:
            query = query.filter(WateringRecord.plot_id == plot_id)

        result = query.first()

        return {
            "total_count": result.total_count or 0,
            "total_volume": float(result.total_volume or 0),
            "avg_volume": float(result.avg_volume or 0),
            "avg_duration": float(result.avg_duration or 0),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }


# 全局浇水服务工厂函数
def get_watering_service(db: Session) -> WateringService:
    """获取浇水服务实例"""
    return WateringService(db)
