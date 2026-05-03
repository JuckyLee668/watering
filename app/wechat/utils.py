# -*- coding: utf-8 -*-
"""WeChat signature and XML message helpers."""

import hashlib
import time
from typing import Any, Dict, Optional, Tuple

from defusedxml import ElementTree as ET

from app.core.config import settings
from app.core.exceptions import WeChatException


class WeChatUtils:
    @staticmethod
    def check_signature(signature: str, timestamp: str, nonce: str) -> bool:
        token = settings.wechat.token
        tmp_str = "".join(sorted([token, timestamp, nonce]))
        return hashlib.sha1(tmp_str.encode("utf-8")).hexdigest() == signature

    @staticmethod
    def parse_xml_message(xml_string: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(xml_string)
            return {child.tag: child.text for child in root}
        except ET.ParseError as exc:
            raise WeChatException(f"XML 消息解析失败: {str(exc)}") from exc

    @staticmethod
    def build_text_message(to_user: str, from_user: str, content: str) -> str:
        template = """<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{create_time}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
        return template.format(
            to_user=to_user,
            from_user=from_user,
            create_time=int(time.time()),
            content=content,
        )

    @staticmethod
    def build_confirm_message(
        to_user: str,
        from_user: str,
        plot_name: str,
        volume: float,
        date: str,
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> str:
        if start_time and end_time:
            time_display = f"{start_time} - {end_time}"
        elif start_time:
            time_display = f"{start_time} 开始"
        else:
            time_display = "未指定具体时间"

        content = (
            "浇水上报确认\n\n"
            f"地块：{plot_name}\n"
            f"水量：{volume} 方\n"
            f"日期：{date}\n"
            f"时间：{time_display}\n\n"
            "回复 1 或 确认：提交\n"
            "回复 2 或 取消：放弃\n"
            "直接重新上报：修改"
        )
        return WeChatUtils.build_text_message(to_user, from_user, content)

    @staticmethod
    def extract_openid(msg_dict: Dict[str, Any]) -> Optional[str]:
        return msg_dict.get("FromUserName")


class WeChatMessageType:
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"
    LINK = "link"
    NEWS = "news"
    EVENT = "event"

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SCAN = "scan"
    CLICK = "click"
    VIEW = "view"


def parse_message_type(msg_dict: Dict[str, Any]) -> Tuple[str, str]:
    return msg_dict.get("MsgType", ""), msg_dict.get("Event", "")
