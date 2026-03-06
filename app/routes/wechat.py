# -*- coding: utf-8 -*-
"""
微信回调接口路由
WeChat Callback API Routes

处理微信服务器的消息回调
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import WeChatException
from app.models.database import get_db
from app.wechat.utils import (
    WeChatUtils,
    WeChatMessageType,
    parse_message_type,
)
from app.services.message_service import get_message_service


# 创建路由
router = APIRouter(prefix="/wechat", tags=["微信接口"])


@router.get("/callback")
async def verify_callback(
    signature: str = Query(..., description="微信加密签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
    echostr: Optional[str] = Query(None, description="随机字符串"),
):
    """
    微信服务器验证回调

    用于首次配置微信开发者时的验证
    """
    # 验证签名
    if not WeChatUtils.check_signature(signature, timestamp, nonce):
        raise WeChatException("签名验证失败", code=403)

    # 返回echostr
    if echostr:
        return echostr

    return "success"


@router.post("/callback")
async def handle_message(
    request: Request,
    signature: str = Query(..., description="微信加密签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
    db: Session = Depends(get_db),
):
    """
    处理微信消息回调

    接收用户发送的消息，调用LLM解析，返回确认消息
    """
    # 验证签名
    if not WeChatUtils.check_signature(signature, timestamp, nonce):
        raise WeChatException("签名验证失败", code=403)

    # 读取消息内容
    body = await request.body()

    try:
        xml_string = body.decode("utf-8")
    except UnicodeDecodeError:
        raise WeChatException("消息解码失败")

    # 解析XML消息
    msg_dict = WeChatUtils.parse_xml_message(xml_string)

    # 提取关键信息
    msg_type, event = parse_message_type(msg_dict)
    openid = WeChatUtils.extract_openid(msg_dict)

    if not openid:
        raise WeChatException("无法获取用户OpenID")

    # 获取发送者ID（公众号ID）
    from_user = msg_dict.get("ToUserName", "")

    # 处理事件消息
    if msg_type == WeChatMessageType.EVENT:
        return await _handle_event(event, openid, from_user, db)

    # 处理文本消息
    if msg_type == WeChatMessageType.TEXT:
        content = msg_dict.get("Content", "")
        return await _handle_text(content, openid, from_user, db)

    # 处理语音消息（微信语音会自动转换为文字）
    if msg_type == WeChatMessageType.VOICE:
        # 尝试获取语音识别结果
        recognition = msg_dict.get("Recognition", "")
        if recognition:
            content = recognition
        else:
            content = msg_dict.get("MediaId", "")
        return await _handle_text(content, openid, from_user, db)

    # 其他消息类型暂不支持
    return WeChatUtils.build_text_message(
        to_user=openid,
        from_user=from_user,
        content="暂不支持此类消息，请发送文字或语音。",
    )


async def _handle_event(
    event: str,
    openid: str,
    from_user: str,
    db: Session,
):
    """处理事件消息"""
    if event == WeChatMessageType.SUBSCRIBE:
        # 用户关注
        welcome_msg = settings.wechat.welcome_message
        return WeChatUtils.build_text_message(
            to_user=openid,
            from_user=from_user,
            content=welcome_msg,
        )

    elif event == WeChatMessageType.UNSUBSCRIBE:
        # 用户取消关注
        return "success"

    # 其他事件
    return "success"


async def _handle_text(
    content: str,
    openid: str,
    from_user: str,
    db: Session,
):
    """
    处理文本消息

    Args:
        content: 消息内容
        openid: 用户OpenID
        from_user: 公众号ID
        db: 数据库会话

    Returns:
        XML格式的响应消息
    """
    # 获取消息服务
    message_service = get_message_service(db)

    try:
        # 处理消息
        reply_content, waiting_confirm = message_service.process_text_message(
            openid=openid,
            content=content,
        )

        # 构建响应消息
        return WeChatUtils.build_text_message(
            to_user=openid,
            from_user=from_user,
            content=reply_content,
        )

    except Exception as e:
        # 发生错误，返回错误消息
        error_msg = f"系统处理出错，请稍后重试。错误：{str(e)}"
        return WeChatUtils.build_text_message(
            to_user=openid,
            from_user=from_user,
            content=error_msg,
        )
