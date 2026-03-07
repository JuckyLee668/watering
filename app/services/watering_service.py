from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.database import Plot, User, WateringRecord
from app.services.plot_catalog_service import get_plot_catalog_service


class WateringService:
    def __init__(self, db: Session):
        self.db = db
        self.plot_catalog = get_plot_catalog_service(db)
        self._plots_synced = False

    @staticmethod
    def _cn_to_int(text: str) -> Optional[int]:
        digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if not text:
            return None
        if text in digits:
            return digits[text]
        if text == "十":
            return 10
        if "十" in text:
            parts = text.split("十")
            tens = digits.get(parts[0], 1) if parts[0] else 1
            ones = digits.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            return tens * 10 + ones
        return None

    @classmethod
    def _plot_aliases(cls, plot_name: str) -> List[str]:
        name = (plot_name or "").strip().replace(" ", "")
        if not name:
            return []
        aliases = {name}
        if name.endswith("号地"):
            prefix = name[:-2]
            if prefix.isdigit():
                cn_map = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
                n = int(prefix)
                if n in cn_map:
                    aliases.add(f"{cn_map[n]}号地")
            else:
                n = cls._cn_to_int(prefix)
                if n is not None:
                    aliases.add(f"{n}号地")
        return list(aliases)

    def get_or_create_user(self, openid: str, name: str = None) -> User:
        user = self.db.query(User).filter(User.openid == openid).first()
        default_name = name or (f"组长_{openid[-8:]}" if openid else "组长")

        def is_placeholder(n: Optional[str]) -> bool:
            val = (n or "").strip()
            return (not val) or val in {"未知用户", "未知组长", "组长"} or val.startswith("组长_")

        if user is None:
            user = User(openid=openid, name=default_name, status=1)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        elif is_placeholder(user.name) and name:
            user.name = default_name
            self.db.commit()
            self.db.refresh(user)

        return user

    def _ensure_plots_from_csv(self):
        if self._plots_synced:
            return
        self.plot_catalog.sync_to_database()
        self._plots_synced = True

    def get_or_create_plot(self, plot_name: str) -> Optional[Plot]:
        self._ensure_plots_from_csv()
        aliases = self._plot_aliases(plot_name)

        for alias in aliases:
            plot = self.db.query(Plot).filter(Plot.plot_name == alias).first()
            if plot:
                return plot

        normalized_aliases = {a.replace(" ", "") for a in aliases}
        for plot in self.db.query(Plot).all():
            if (plot.plot_name or "").replace(" ", "") in normalized_aliases:
                return plot

        return self.db.query(Plot).filter(Plot.plot_name.like(f"%{plot_name}%")).first()

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
        duration_minutes = None
        if start_time and end_time:
            start_dt = datetime.combine(date.today(), start_time)
            end_dt = datetime.combine(date.today(), end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)

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
        query = self.db.query(WateringRecord).filter(WateringRecord.user_id == user_id)
        if start_date:
            query = query.filter(WateringRecord.operation_date >= start_date)
        if end_date:
            query = query.filter(WateringRecord.operation_date <= end_date)
        return query.order_by(desc(WateringRecord.operation_date), desc(WateringRecord.create_time)).limit(limit).all()

    def get_plot_records(
        self,
        plot_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[WateringRecord]:
        query = self.db.query(WateringRecord).filter(WateringRecord.plot_id == plot_id)
        if start_date:
            query = query.filter(WateringRecord.operation_date >= start_date)
        if end_date:
            query = query.filter(WateringRecord.operation_date <= end_date)
        return query.order_by(desc(WateringRecord.operation_date), desc(WateringRecord.create_time)).limit(limit).all()

    def get_all_records(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[int] = None,
        plot_id: Optional[int] = None,
        owner_name: Optional[str] = None,
        confirm_status: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WateringRecord]:
        query = self.db.query(WateringRecord)
        if start_date:
            query = query.filter(WateringRecord.operation_date >= start_date)
        if end_date:
            query = query.filter(WateringRecord.operation_date <= end_date)
        if user_id:
            query = query.filter(WateringRecord.user_id == user_id)
        if plot_id:
            query = query.filter(WateringRecord.plot_id == plot_id)
        if owner_name:
            query = query.join(Plot, WateringRecord.plot_id == Plot.id).filter(Plot.owner_name.like(f"%{owner_name}%"))
        if confirm_status is not None:
            query = query.filter(WateringRecord.confirm_status == confirm_status)
        return query.order_by(desc(WateringRecord.operation_date), desc(WateringRecord.create_time)).offset(offset).limit(limit).all()

    def get_record_by_id(self, record_id: int) -> Optional[WateringRecord]:
        return self.db.query(WateringRecord).filter(WateringRecord.id == record_id).first()

    def update_confirm_status(self, record_id: int, confirm_status: int) -> Optional[WateringRecord]:
        record = self.get_record_by_id(record_id)
        if not record:
            return None
        record.confirm_status = confirm_status
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_statistics(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[int] = None,
        plot_id: Optional[int] = None,
    ) -> Dict[str, Any]:
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


def get_watering_service(db: Session) -> WateringService:
    return WateringService(db)
