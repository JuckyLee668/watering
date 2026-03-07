import threading
import time
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings


class WeChatUserService:
    """Fetch and cache WeChat official account user profile."""

    TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    USER_INFO_URL = "https://api.weixin.qq.com/cgi-bin/user/info"

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0
        self._nickname_cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._nickname_ttl = 3600
        self._refreshing: set[str] = set()

    def _get_access_token(self) -> Optional[str]:
        now = time.time()
        with self._lock:
            if self._token and now < self._token_expire_at:
                return self._token

        app_id = settings.wechat.app_id
        app_secret = settings.wechat.app_secret
        if not app_id or not app_secret:
            return None

        try:
            with httpx.Client(timeout=1.5) as client:
                resp = client.get(
                    self.TOKEN_URL,
                    params={
                        "grant_type": "client_credential",
                        "appid": app_id,
                        "secret": app_secret,
                    },
                )
                data = resp.json()
            token = data.get("access_token")
            expires_in = int(data.get("expires_in", 0))
            if not token or expires_in <= 0:
                logger.warning("wechat token fetch failed: {}", data)
                return None

            with self._lock:
                self._token = token
                self._token_expire_at = time.time() + max(expires_in - 120, 60)
            return token
        except Exception as exc:
            logger.warning("wechat token request error: {}", str(exc))
            return None

    def _fetch_and_cache_nickname(self, openid: str) -> Optional[str]:
        token = self._get_access_token()
        if not token:
            return None

        try:
            with httpx.Client(timeout=1.2) as client:
                resp = client.get(
                    self.USER_INFO_URL,
                    params={
                        "access_token": token,
                        "openid": openid,
                        "lang": "zh_CN",
                    },
                )
                data = resp.json()

            nickname = data.get("nickname")
            if not nickname:
                logger.warning("wechat user info missing nickname: openid={}, body={}", openid, data)
                return None

            nickname = str(nickname).strip()
            if not nickname:
                return None

            with self._lock:
                self._nickname_cache[openid] = (nickname, time.time() + self._nickname_ttl)
            return nickname
        except Exception as exc:
            logger.warning("wechat user info request error: openid={}, err={}", openid, str(exc))
            return None

    def _refresh_nickname_async(self, openid: str) -> None:
        with self._lock:
            if openid in self._refreshing:
                return
            self._refreshing.add(openid)

        def _run() -> None:
            try:
                self._fetch_and_cache_nickname(openid)
            finally:
                with self._lock:
                    self._refreshing.discard(openid)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def get_user_nickname(self, openid: str, blocking: bool = False) -> Optional[str]:
        if not openid:
            return None

        now = time.time()
        with self._lock:
            cached = self._nickname_cache.get(openid)
            if cached and now < cached[1]:
                return cached[0]

        if blocking:
            return self._fetch_and_cache_nickname(openid)

        # Never block WeChat passive reply path on external API.
        self._refresh_nickname_async(openid)
        return None


_wechat_user_service: Optional[WeChatUserService] = None


def get_wechat_user_service() -> WeChatUserService:
    global _wechat_user_service
    if _wechat_user_service is None:
        _wechat_user_service = WeChatUserService()
    return _wechat_user_service
