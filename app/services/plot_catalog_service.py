# -*- coding: utf-8 -*-
"""
地块目录服务
Plot Catalog Service

负责从CSV文件加载地块信息，并同步到数据库。
"""

import csv
from pathlib import Path
from typing import List, Dict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import Plot


class PlotCatalogService:
    """地块CSV目录服务"""

    def __init__(self, db: Session):
        self.db = db

    def _csv_path(self) -> Path:
        return Path(settings.plots.csv_path)

    def load_from_csv(self) -> List[Dict[str, str]]:
        """读取CSV并返回地块列表"""
        csv_path = self._csv_path()
        if not csv_path.exists():
            return []

        plots: List[Dict[str, str]] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                plot_name = (row.get("plot_name") or "").strip()
                plot_code = (row.get("plot_code") or "").strip()
                if not plot_name or not plot_code:
                    continue

                plots.append(
                    {
                        "plot_name": plot_name,
                        "plot_code": plot_code,
                        "area": (row.get("area") or "").strip(),
                        "location": (row.get("location") or "").strip(),
                        "owner_name": (row.get("owner_name") or "").strip(),
                        "status": (row.get("status") or "1").strip(),
                    }
                )

        return plots

    def sync_to_database(self) -> int:
        """将CSV中的地块同步到数据库（按plot_code upsert）"""
        rows = self.load_from_csv()
        synced = 0

        for row in rows:
            existing = self.db.query(Plot).filter(Plot.plot_code == row["plot_code"]).first()

            area = float(row["area"]) if row["area"] else None
            status = int(row["status"]) if row["status"] else 1

            if existing:
                existing.plot_name = row["plot_name"]
                existing.area = area
                existing.location = row["location"] or None
                existing.owner_name = row["owner_name"] or None
                existing.status = status
            else:
                self.db.add(
                    Plot(
                        plot_name=row["plot_name"],
                        plot_code=row["plot_code"],
                        area=area,
                        location=row["location"] or None,
                        owner_name=row["owner_name"] or None,
                        status=status,
                    )
                )
            synced += 1

        self.db.commit()
        return synced

    def get_standard_names(self) -> List[str]:
        """从CSV获取标准地块名称列表"""
        return [p["plot_name"] for p in self.load_from_csv()]


def get_plot_catalog_service(db: Session) -> PlotCatalogService:
    return PlotCatalogService(db)
