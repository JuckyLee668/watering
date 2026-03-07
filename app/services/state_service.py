import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.core.config import settings
from app.models.database import SessionLocal, UserPendingState, init_database


class UserStateManager:
    STATE_IDLE = "idle"
    STATE_WAITING_CONFIRM = "waiting_confirm"

    def __init__(self):
        init_database()
        self._pending_timeout = settings.state.pending_timeout
        self._state_ttl = settings.state.user_state_ttl

    def _cleanup_expired(self, db) -> None:
        now = datetime.now()
        expired = (
            db.query(UserPendingState)
            .filter(UserPendingState.expires_at.isnot(None))
            .filter(UserPendingState.expires_at <= now)
            .all()
        )
        for row in expired:
            row.state = self.STATE_IDLE
            row.pending_data = None
            row.expires_at = None
        if expired:
            db.commit()

    def _get_or_create_state(self, db, openid: str) -> UserPendingState:
        row = db.query(UserPendingState).filter(UserPendingState.openid == openid).first()
        if row is None:
            row = UserPendingState(
                openid=openid,
                state=self.STATE_IDLE,
                pending_data=None,
                expires_at=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    def save_pending_data(self, openid: str, parsed_data: Dict[str, Any]) -> str:
        pending_id = str(uuid.uuid4())
        pending_data = dict(parsed_data)
        pending_data.update(
            {
                "pending_id": pending_id,
                "openid": openid,
                "create_time": datetime.now().isoformat(),
            }
        )

        with SessionLocal() as db:
            self._cleanup_expired(db)
            row = self._get_or_create_state(db, openid)
            row.state = self.STATE_WAITING_CONFIRM
            row.pending_data = json.dumps(pending_data, ensure_ascii=False)
            row.expires_at = datetime.now() + timedelta(seconds=self._pending_timeout)
            db.commit()

        return pending_id

    def get_pending_data(self, openid: str) -> Optional[Dict[str, Any]]:
        with SessionLocal() as db:
            self._cleanup_expired(db)
            row = db.query(UserPendingState).filter(UserPendingState.openid == openid).first()
            if not row or row.state != self.STATE_WAITING_CONFIRM or not row.pending_data:
                return None
            return json.loads(row.pending_data)

    def delete_pending_data(self, openid: str) -> bool:
        with SessionLocal() as db:
            row = db.query(UserPendingState).filter(UserPendingState.openid == openid).first()
            if row:
                row.state = self.STATE_IDLE
                row.pending_data = None
                row.expires_at = None
                db.commit()
        return True

    def get_user_state(self, openid: str) -> str:
        with SessionLocal() as db:
            self._cleanup_expired(db)
            row = db.query(UserPendingState).filter(UserPendingState.openid == openid).first()
            return row.state if row and row.state else self.STATE_IDLE

    def set_user_state(self, openid: str, state: str, ttl: Optional[int] = None) -> bool:
        with SessionLocal() as db:
            self._cleanup_expired(db)
            row = self._get_or_create_state(db, openid)
            row.state = state
            if ttl:
                row.expires_at = datetime.now() + timedelta(seconds=ttl)
            elif state == self.STATE_IDLE:
                row.expires_at = None
            else:
                row.expires_at = datetime.now() + timedelta(seconds=self._state_ttl)
            if state != self.STATE_WAITING_CONFIRM:
                row.pending_data = None
            db.commit()
        return True

    def is_waiting_confirm(self, openid: str) -> bool:
        return self.get_user_state(openid) == self.STATE_WAITING_CONFIRM


_state_manager: Optional[UserStateManager] = None


def get_state_manager() -> UserStateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = UserStateManager()
    return _state_manager
