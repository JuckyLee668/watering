import threading
import time
from typing import Optional, Dict, Any

import httpx
from loguru import logger

from app.core.config import settings


class WeChatMenuService:
    """Manage WeChat official account custom menus."""

    TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    CREATE_MENU_URL = "https://api.weixin.qq.com/cgi-bin/menu/create"
    GET_MENU_URL = "https://api.weixin.qq.com/cgi-bin/menu/get"
    DELETE_MENU_URL = "https://api.weixin.qq.com/cgi-bin/menu/delete"

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0
        self._lock = threading.Lock()

    def _get_access_token(self) -> Optional[str]:
        """Fetch and cache access_token."""
        now = time.time()

        with self._lock:
            if self._token and now < self._token_expire_at:
                return self._token

        app_id = settings.wechat.app_id
        app_secret = settings.wechat.app_secret

        if not app_id or not app_secret:
            logger.warning("wechat app_id or app_secret not configured")
            return None

        try:
            with httpx.Client(timeout=2) as client:
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

            if not token:
                logger.warning("wechat token fetch failed: {}", data)
                return None

            with self._lock:
                self._token = token
                self._token_expire_at = time.time() + max(expires_in - 120, 60)

            return token

        except Exception as exc:
            logger.warning("wechat token request error: {}", str(exc))
            return None

    def create_menu(self, menu_data: Dict[str, Any]) -> bool:
        """Create custom menu."""
        token = self._get_access_token()
        if not token:
            return False

        try:
            with httpx.Client(timeout=3) as client:
                resp = client.post(
                    self.CREATE_MENU_URL,
                    params={"access_token": token},
                    json=menu_data,
                )

                data = resp.json()

            if data.get("errcode") == 0:
                logger.info("wechat menu created successfully")
                return True

            logger.warning("wechat menu create failed: {}", data)
            return False

        except Exception as exc:
            logger.warning("wechat menu create error: {}", str(exc))
            return False

    def get_menu(self) -> Optional[Dict[str, Any]]:
        """Fetch current menu."""
        token = self._get_access_token()
        if not token:
            return None

        try:
            with httpx.Client(timeout=2) as client:
                resp = client.get(
                    self.GET_MENU_URL,
                    params={"access_token": token},
                )

                data = resp.json()

            return data

        except Exception as exc:
            logger.warning("wechat get menu error: {}", str(exc))
            return None

    def delete_menu(self) -> bool:
        """Delete custom menu."""
        token = self._get_access_token()
        if not token:
            return False

        try:
            with httpx.Client(timeout=2) as client:
                resp = client.get(
                    self.DELETE_MENU_URL,
                    params={"access_token": token},
                )

                data = resp.json()

            if data.get("errcode") == 0:
                logger.info("wechat menu deleted successfully")
                return True

            logger.warning("wechat menu delete failed: {}", data)
            return False

        except Exception as exc:
            logger.warning("wechat delete menu error: {}", str(exc))
            return False


_wechat_menu_service: Optional[WeChatMenuService] = None


def get_wechat_menu_service() -> WeChatMenuService:
    global _wechat_menu_service

    if _wechat_menu_service is None:
        _wechat_menu_service = WeChatMenuService()

    return _wechat_menu_service