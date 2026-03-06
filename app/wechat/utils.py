# -*- coding: utf-8 -*-
"""
微信工具函数
WeChat Utility Functions

提供微信签名验证、消息解析等工具函数
"""

import hashlib
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Tuple

from app.core.config import settings
from app.core.exceptions import WeChatException


class WeChatUtils:
    """微信工具类"""

    @staticmethod
    def check_signature(signature: str, timestamp: str, nonce: str) -> bool:
        """
        验证微信签名

        Args:
            signature: 微信加密签名
            timestamp: 时间戳
            nonce: 随机数

        Returns:
            签名是否正确
        """
        token = settings.wechat.token
        tmp_list = sorted([token, timestamp, nonce])
        tmp_str = "".join(tmp_list)
        tmp_str = hashlib.sha1(tmp_str.encode("utf-8")).hexdigest()

        return tmp_str == signature

    @staticmethod
    def parse_xml_message(xml_string: str) -> Dict[str, Any]:
        """
        解析微信XML消息

        Args:
            xml_string: 微信推送的XML消息

        Returns:
            解析后的消息字典
        """
        try:
            root = ET.fromstring(xml_string)

            # 提取所有字段
            msg_dict = {}
            for child in root:
                msg_dict[child.tag] = child.text

            return msg_dict

        except ET.ParseError as e:
            raise WeChatException(f"XML消息解析失败: {str(e)}")

    @staticmethod
    def build_text_message(
        to_user: str, from_user: str, content: str
    ) -> str:
        """
        构建文本消息XML

        Args:
            to_user: 接收者OpenID
            from_user: 发送者OpenID（公众号ID）
            content: 消息内容

        Returns:
            文本消息XML字符串
        """
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
        """
        构建确认消息

        Args:
            to_user: 接收者OpenID
            from_user: 发送者OpenID
            plot_name: 地块名称
            volume: 浇水方数
            date: 日期
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            确认消息XML
        """
        # 格式化时间显示
        if start_time and end_time:
            time_display = f"{start_time} - {end_time}"
        elif start_time:
            time_display = f"{start_time}开始"
        else:
            time_display = "未指定具体时间"

        content = f"""📋 浇水上报确认

地块：{plot_name}
水量：{volume}方
日期：{date}
时间：{time_display}

━━━━━━━━━━━━━━━
请回复：
✅ 确认 - 回复"1"或"确认"
❌ 取消 - 回复"2"或"取消"
🔄 修改 - 直接重新上报
━━━━━━━━━━━━━━━

💡 提示：超时5分钟将自动取消"""

        return WeChatUtils.build_text_message(to_user, from_user, content)

    @staticmethod
    def extract_openid(msg_dict: Dict[str, Any]) -> Optional[str]:
        """
        从消息中提取OpenID

        Args:
            msg_dict: 消息字典

        Returns:
            OpenID
        """
        return msg_dict.get("FromUserName")


class WeChatMessageType:
    """微信消息类型常量"""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"
    LINK = "link"
    NEWS = "news"
    EVENT = "event"

    # 事件类型
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SCAN = "scan"
    CLICK = "click"
    VIEW = "view"


def parse_message_type(msg_dict: Dict[str, Any]) -> Tuple[str, str]:
    """
    解析消息类型

    Args:
        msg_dict: 消息字典

    Returns:
        (消息类型, 事件类型)
    """
    msg_type = msg_dict.get("MsgType", "")
    event = msg_dict.get("Event", "")
    return msg_type, event
