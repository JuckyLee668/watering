# -*- coding: utf-8 -*-
"""
数据库模型定义
Database Models Definition

包含用户、地块、浇水记录等数据模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    BigInteger,
    SmallInteger,
    DateTime,
    Date,
    Time,
    DECIMAL,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker, declared_attr
from sqlalchemy.pool import QueuePool

from app.core.config import settings

# 创建基础类
Base = declarative_base()


class TimestampMixin:
    """时间戳混入类"""

    @declared_attr
    def create_time(cls):
        return Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    @declared_attr
    def update_time(cls):
        return Column(
            DateTime,
            default=datetime.now,
            onupdate=datetime.now,
            nullable=False,
            comment="更新时间",
        )


class User(Base, TimestampMixin):
    """
    用户表 - 作业人员信息
    """

    __tablename__ = "users"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")

    # 微信标识
    openid = Column(
        String(64), unique=True, nullable=False, index=True, comment="微信OpenID"
    )

    # 用户信息
    name = Column(String(50), nullable=False, comment="真实姓名")
    phone = Column(String(20), nullable=True, comment="手机号")
    department = Column(String(50), nullable=True, comment="所属部门/班组")

    # 状态
    status = Column(
        SmallInteger,
        default=1,
        nullable=False,
        comment="状态：1-在职，0-离职",
    )

    # 关联关系
    watering_records = relationship(
        "WateringRecord", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, openid={self.openid})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "openid": self.openid,
            "name": self.name,
            "phone": self.phone,
            "department": self.department,
            "status": self.status,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class Plot(Base, TimestampMixin):
    """
    地块表 - 农田地块信息
    """

    __tablename__ = "plots"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="地块ID")

    # 地块信息
    plot_name = Column(
        String(50), nullable=False, index=True, comment="地块名称"
    )
    plot_code = Column(
        String(20), unique=True, nullable=False, index=True, comment="地块编码"
    )
    area = Column(DECIMAL(10, 2), nullable=True, comment="面积(亩)")
    location = Column(String(100), nullable=True, comment="位置描述")

    # 状态
    status = Column(
        SmallInteger,
        default=1,
        nullable=False,
        comment="状态：1-启用，0-停用",
    )

    # 关联关系
    watering_records = relationship(
        "WateringRecord", back_populates="plot", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_plot_status", "status"),
        Index("idx_plot_name_status", "plot_name", "status"),
    )

    def __repr__(self):
        return f"<Plot(id={self.id}, name={self.plot_name}, code={self.plot_code})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "plot_name": self.plot_name,
            "plot_code": self.plot_code,
            "area": float(self.area) if self.area else None,
            "location": self.location,
            "status": self.status,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class WateringRecord(Base, TimestampMixin):
    """
    浇水记录表 - 浇水作业记录
    """

    __tablename__ = "watering_records"

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")

    # 外键关联
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    plot_id = Column(
        Integer,
        ForeignKey("plots.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="地块ID",
    )

    # 浇水数据
    volume = Column(
        DECIMAL(10, 2), nullable=False, comment="浇水方数(m³)"
    )
    operation_date = Column(Date, nullable=False, index=True, comment="作业日期")
    start_time = Column(Time, nullable=True, comment="开始时间")
    end_time = Column(Time, nullable=True, comment="结束时间")
    duration_minutes = Column(Integer, nullable=True, comment="时长(分钟)")

    # 原始数据追溯
    raw_input = Column(Text, nullable=True, comment="用户原始输入")

    # 确认状态
    confirm_status = Column(
        SmallInteger,
        default=0,
        nullable=False,
        comment="确认状态：1-已确认，0-待确认",
    )

    # 备注
    remark = Column(String(500), nullable=True, comment="备注")

    # 关联关系
    user = relationship("User", back_populates="watering_records")
    plot = relationship("Plot", back_populates="watering_records")

    # 索引
    __table_args__ = (
        Index("idx_record_user_date", "user_id", "operation_date"),
        Index("idx_record_plot_date", "plot_id", "operation_date"),
        Index("idx_record_confirm", "confirm_status", "operation_date"),
    )

    def __repr__(self):
        return f"<WateringRecord(id={self.id}, user_id={self.user_id}, volume={self.volume})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else None,
            "plot_id": self.plot_id,
            "plot_name": self.plot.plot_name if self.plot else None,
            "volume": float(self.volume) if self.volume else None,
            "operation_date": self.operation_date.isoformat()
            if self.operation_date
            else None,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "duration_minutes": self.duration_minutes,
            "raw_input": self.raw_input,
            "confirm_status": self.confirm_status,
            "remark": self.remark,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


# ============================================================
# 数据库连接和会话管理
# ============================================================


def get_database_url() -> str:
    """获取数据库连接URL"""
    db_config = settings.database
    return (
        f"{db_config.driver}://{db_config.username}:{db_config.password}"
        f"@{db_config.host}:{db_config.port}/{db_config.database}"
        f"?charset={db_config.charset}"
    )


def create_engine_and_session():
    """创建数据库引擎和会话"""
    database_url = get_database_url()

    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=settings.database.pool_pre_ping,
        echo=settings.database.echo,
        pool_recycle=3600,
    )

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    return engine, SessionLocal


# 全局引擎和会话工厂
engine, SessionLocal = create_engine_and_session()


def get_db():
    """
    获取数据库会话的依赖函数
    用于FastAPI的依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """初始化数据库 - 创建所有表"""
    Base.metadata.create_all(bind=engine)
    print("数据库表创建成功！")


def drop_database():
    """删除所有数据库表"""
    Base.metadata.drop_all(bind=engine)
    print("数据库表已删除！")
