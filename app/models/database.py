from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Generator, Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, declared_attr, relationship, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

Base = declarative_base()


class TimestampMixin:
    @declared_attr
    def create_time(cls):
        return Column(DateTime, default=datetime.now, nullable=False)

    @declared_attr
    def update_time(cls):
        return Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=True)
    department = Column(String(50), nullable=True)
    status = Column(SmallInteger, default=1, nullable=False)

    watering_records = relationship("WateringRecord", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
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
    __tablename__ = "plots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_name = Column(String(50), nullable=False, index=True)
    plot_code = Column(String(20), unique=True, nullable=False, index=True)
    area = Column(DECIMAL(10, 2), nullable=True)
    location = Column(String(100), nullable=True)
    owner_name = Column(String(100), nullable=True)
    status = Column(SmallInteger, default=1, nullable=False)

    watering_records = relationship("WateringRecord", back_populates="plot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_plot_status", "status"),
        Index("idx_plot_name_status", "plot_name", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plot_name": self.plot_name,
            "plot_code": self.plot_code,
            "area": float(self.area) if self.area is not None else None,
            "location": self.location,
            "owner_name": self.owner_name,
            "status": self.status,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class WateringRecord(Base, TimestampMixin):
    __tablename__ = "watering_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=True, index=True)

    volume = Column(DECIMAL(10, 2), nullable=False)
    operation_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    raw_input = Column(Text, nullable=True)
    confirm_status = Column(SmallInteger, default=0, nullable=False)
    remark = Column(String(500), nullable=True)

    user = relationship("User", back_populates="watering_records")
    plot = relationship("Plot", back_populates="watering_records")

    __table_args__ = (
        Index("idx_record_user_date", "user_id", "operation_date"),
        Index("idx_record_plot_date", "plot_id", "operation_date"),
        Index("idx_record_confirm", "confirm_status", "operation_date"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else None,
            "leader_name": self.user.name if self.user else None,
            "leader_openid": self.user.openid if self.user else None,
            "plot_id": self.plot_id,
            "plot_name": self.plot.plot_name if self.plot else None,
            "plot_owner_name": self.plot.owner_name if self.plot else None,
            "volume": float(self.volume) if isinstance(self.volume, Decimal) else self.volume,
            "operation_date": self.operation_date.isoformat() if self.operation_date else None,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "duration_minutes": self.duration_minutes,
            "raw_input": self.raw_input,
            "confirm_status": self.confirm_status,
            "remark": self.remark,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class UserPendingState(Base, TimestampMixin):
    __tablename__ = "user_pending_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False, index=True)
    state = Column(String(32), nullable=False, default="idle")
    pending_data = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("idx_pending_openid_state", "openid", "state"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "openid": self.openid,
            "state": self.state,
            "pending_data": self.pending_data,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class WeChatMessageLog(Base, TimestampMixin):
    __tablename__ = "wechat_message_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    msg_type = Column(String(32), nullable=False, default="text")
    direction = Column(String(16), nullable=False, default="in")
    content = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="success")
    error = Column(String(500), nullable=True)

    __table_args__ = (
        Index("idx_chatlog_openid_time", "openid", "create_time"),
        Index("idx_chatlog_direction_time", "direction", "create_time"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "openid": self.openid,
            "msg_type": self.msg_type,
            "direction": self.direction,
            "content": self.content,
            "status": self.status,
            "error": self.error,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


def get_database_url() -> str:
    db_config = settings.database
    if db_config.url:
        return db_config.url
    if db_config.driver.startswith("sqlite"):
        return f"sqlite:///{db_config.sqlite_path}"
    return (
        f"{db_config.driver}://{db_config.username}:{db_config.password}"
        f"@{db_config.host}:{db_config.port}/{db_config.database}"
        f"?charset={db_config.charset}"
    )


def _create_engine(database_url: str):
    if database_url.startswith("sqlite"):
        db_file = database_url.replace("sqlite:///", "", 1)
        if db_file and db_file != ":memory:":
            db_dir = os.path.dirname(db_file)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=settings.database.echo,
        )

    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=settings.database.pool_pre_ping,
        echo=settings.database.echo,
        pool_recycle=3600,
    )


def create_engine_and_session():
    database_url = get_database_url()
    engine = _create_engine(database_url)

    if not database_url.startswith("sqlite") and settings.database.fallback_to_sqlite:
        try:
            with engine.connect():
                pass
        except Exception as exc:
            fallback_url = f"sqlite:///{settings.database.sqlite_path}"
            print(f"MySQL connect failed, fallback to SQLite: {exc}")
            engine = _create_engine(fallback_url)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


engine, SessionLocal = create_engine_and_session()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()


def _ensure_schema_updates() -> None:
    """Lightweight runtime schema patching for backward-compatible upgrades."""
    inspector = inspect(engine)
    if "plots" not in inspector.get_table_names():
        return

    plot_columns = {c["name"] for c in inspector.get_columns("plots")}
    with engine.begin() as conn:
        if "owner_name" not in plot_columns:
            conn.execute(text("ALTER TABLE plots ADD COLUMN owner_name VARCHAR(100)"))


def drop_database() -> None:
    Base.metadata.drop_all(bind=engine)
