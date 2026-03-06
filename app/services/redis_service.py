# -*- coding: utf-8 -*-
"""
Redis状态管理服务
Redis State Management Service

管理用户的待确认状态、会话状态等
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

import redis

from app.core.config import settings
from app.core.exceptions import RedisException


class RedisClient:
    """Redis客户端封装"""

    def __init__(self):
        """初始化Redis连接"""
        try:
            self._client = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password if settings.redis.password else None,
                db=settings.redis.db,
                decode_responses=settings.redis.decode_responses,
                encoding=settings.redis.encoding,
            )
            # 测试连接
            self._client.ping()
        except redis.ConnectionError as e:
            raise RedisException(f"Redis连接失败: {str(e)}")

    def get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        return self._client


# 全局Redis客户端
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """获取Redis客户端实例"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


class UserStateManager:
    """用户状态管理器"""

    # 用户状态常量
    STATE_IDLE = "idle"
    STATE_WAITING_CONFIRM = "waiting_confirm"

    # Redis Key前缀
    PREFIX_PENDING = "watering:pending:"
    PREFIX_USER_STATE = "user:state:"

    def __init__(self):
        self._client = get_redis_client().get_client()
        self._pending_timeout = settings.redis.pending_timeout
        self._state_ttl = settings.redis.user_state_ttl

    def save_pending_data(
        self,
        openid: str,
        parsed_data: Dict[str, Any],
    ) -> str:
        """
        保存待确认的浇水数据

        Args:
            openid: 用户OpenID
            parsed_data: 解析后的数据

        Returns:
            pending_id: 待确认记录ID
        """
        # 生成唯一的pending_id
        pending_id = str(uuid.uuid4())

        # 构建存储数据
        pending_data = {
            "pending_id": pending_id,
            "openid": openid,
            "plot_name": parsed_data.get("plot_name"),
            "volume": parsed_data.get("volume"),
            "date": parsed_data.get("date"),
            "start_time": parsed_data.get("start_time"),
            "end_time": parsed_data.get("end_time"),
            "confidence": parsed_data.get("confidence", 0),
            "raw_input": parsed_data.get("raw_input", ""),
            "create_time": datetime.now().isoformat(),
        }

        # 存储到Redis
        key = f"{self.PREFIX_PENDING}{openid}"
        try:
            # 存储待确认数据
            self._client.setex(
                key,
                self._pending_timeout,
                json.dumps(pending_data, ensure_ascii=False),
            )

            # 更新用户状态
            self._client.setex(
                f"{self.PREFIX_USER_STATE}{openid}",
                self._pending_timeout,
                self.STATE_WAITING_CONFIRM,
            )
        except redis.RedisError as e:
            raise RedisException(f"保存待确认数据失败: {str(e)}")

        return pending_id

    def get_pending_data(self, openid: str) -> Optional[Dict[str, Any]]:
        """
        获取用户的待确认数据

        Args:
            openid: 用户OpenID

        Returns:
            待确认数据字典，如果不存在则返回None
        """
        key = f"{self.PREFIX_PENDING}{openid}"
        try:
            data = self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            raise RedisException(f"获取待确认数据失败: {str(e)}")

    def delete_pending_data(self, openid: str) -> bool:
        """
        删除待确认数据

        Args:
            openid: 用户OpenID

        Returns:
            是否删除成功
        """
        try:
            # 删除待确认数据
            pending_key = f"{self.PREFIX_PENDING}{openid}"
            self._client.delete(pending_key)

            # 重置用户状态
            state_key = f"{self.PREFIX_USER_STATE}{openid}"
            self._client.delete(state_key)

            return True
        except redis.RedisError as e:
            raise RedisException(f"删除待确认数据失败: {str(e)}")

    def get_user_state(self, openid: str) -> str:
        """
        获取用户当前状态

        Args:
            openid: 用户OpenID

        Returns:
            用户状态
        """
        key = f"{self.PREFIX_USER_STATE}{openid}"
        try:
            state = self._client.get(key)
            return state or self.STATE_IDLE
        except redis.RedisError as e:
            raise RedisException(f"获取用户状态失败: {str(e)}")

    def set_user_state(self, openid: str, state: str, ttl: Optional[int] = None) -> bool:
        """
        设置用户状态

        Args:
            openid: 用户OpenID
            state: 状态值
            ttl: 过期时间（秒）

        Returns:
            是否设置成功
        """
        key = f"{self.PREFIX_USER_STATE}{openid}"
        expire_time = ttl or self._state_ttl

        try:
            self._client.setex(key, expire_time, state)
            return True
        except redis.RedisError as e:
            raise RedisException(f"设置用户状态失败: {str(e)}")

    def is_waiting_confirm(self, openid: str) -> bool:
        """
        检查用户是否处于待确认状态

        Args:
            openid: 用户OpenID

        Returns:
            是否处于待确认状态
        """
        state = self.get_user_state(openid)
        return state == self.STATE_WAITING_CONFIRM


# 全局状态管理器实例
_state_manager: Optional[UserStateManager] = None


def get_state_manager() -> UserStateManager:
    """获取用户状态管理器实例"""
    global _state_manager
    if _state_manager is None:
        _state_manager = UserStateManager()
    return _state_manager
