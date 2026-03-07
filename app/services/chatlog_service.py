from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.database import WeChatMessageLog


class ChatLogService:
    def __init__(self, db: Session):
        self.db = db

    def create_log(
        self,
        openid: Optional[str],
        msg_type: str,
        direction: str,
        content: str,
        status: str = "success",
        error: Optional[str] = None,
    ) -> WeChatMessageLog:
        log = WeChatMessageLog(
            openid=openid,
            msg_type=msg_type,
            direction=direction,
            content=content,
            status=status,
            error=error,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_logs(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        openid: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[WeChatMessageLog]:
        query = self.db.query(WeChatMessageLog)
        if start_date:
            query = query.filter(WeChatMessageLog.create_time >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(WeChatMessageLog.create_time <= datetime.combine(end_date, time.max))
        if openid:
            query = query.filter(WeChatMessageLog.openid == openid)
        if direction:
            query = query.filter(WeChatMessageLog.direction == direction)
        return query.order_by(desc(WeChatMessageLog.id)).offset(offset).limit(limit).all()


def get_chatlog_service(db: Session) -> ChatLogService:
    return ChatLogService(db)
