from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import WeChatException
from app.models.database import get_db
from app.services.chatlog_service import get_chatlog_service
from app.services.message_service import get_message_service
from app.wechat.utils import WeChatMessageType, WeChatUtils, parse_message_type


router = APIRouter(prefix="/wechat", tags=["wechat"])


def _safe_log(
    db: Session,
    openid: Optional[str],
    msg_type: str,
    direction: str,
    content: str,
    status: str = "success",
    error: Optional[str] = None,
) -> None:
    try:
        get_chatlog_service(db).create_log(
            openid=openid,
            msg_type=msg_type,
            direction=direction,
            content=content,
            status=status,
            error=error,
        )
    except Exception as exc:
        logger.warning("write chat log failed: {}", str(exc))


@router.get("/callback", response_class=PlainTextResponse)
async def verify_callback(
    request: Request,
    signature: Optional[str] = Query(None, description="wechat signature"),
    timestamp: Optional[str] = Query(None, description="wechat timestamp"),
    nonce: Optional[str] = Query(None, description="wechat nonce"),
    echostr: Optional[str] = Query(None, description="wechat echo string"),
):
    # Human/browser health check without WeChat signature params.
    if not signature or not timestamp or not nonce:
        client_ip = request.client.host if request.client else "-"
        logger.info("wechat callback health check: client_ip={}", client_ip)
        return PlainTextResponse(content="wechat callback alive")

    logger.info(
        "wechat verify request: timestamp={}, nonce_len={}, echostr_len={}",
        timestamp,
        len(nonce or ""),
        len(echostr or ""),
    )
    if not WeChatUtils.check_signature(signature, timestamp, nonce):
        logger.warning("wechat verify failed: signature mismatch")
        raise WeChatException("signature verification failed", code=403)

    if echostr is not None:
        logger.info("wechat verify success")
        return PlainTextResponse(content=echostr)
    return PlainTextResponse(content="success")


@router.post("/callback", response_class=PlainTextResponse)
async def handle_message(
    request: Request,
    signature: str = Query(..., description="wechat signature"),
    timestamp: str = Query(..., description="wechat timestamp"),
    nonce: str = Query(..., description="wechat nonce"),
    db: Session = Depends(get_db),
):
    if not WeChatUtils.check_signature(signature, timestamp, nonce):
        _safe_log(db, None, "system", "in", "signature verification failed", status="error", error="signature mismatch")
        raise WeChatException("signature verification failed", code=403)

    body = await request.body()
    try:
        xml_string = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        _safe_log(db, None, "system", "in", "message decode failed", status="error", error=str(exc))
        raise WeChatException("message decode failed") from exc

    msg_dict = WeChatUtils.parse_xml_message(xml_string)
    msg_type, event = parse_message_type(msg_dict)
    openid = WeChatUtils.extract_openid(msg_dict)
    if not openid:
        _safe_log(db, None, msg_type or "unknown", "in", xml_string[:1000], status="error", error="openid missing")
        raise WeChatException("openid missing")

    from_user = msg_dict.get("ToUserName", "")

    if msg_type == WeChatMessageType.EVENT:
        _safe_log(db, openid, "event", "in", event or "event")
        return await _handle_event(event, openid, from_user, db)

    if msg_type == WeChatMessageType.TEXT:
        content = msg_dict.get("Content", "")
        _safe_log(db, openid, "text", "in", content)
        return await _handle_text(content, openid, from_user, db)

    if msg_type == WeChatMessageType.VOICE:
        recognition = msg_dict.get("Recognition", "")
        content = recognition if recognition else msg_dict.get("MediaId", "")
        _safe_log(db, openid, "voice", "in", content)
        return await _handle_text(content, openid, from_user, db)

    reply_content = "暂不支持此类消息，请发送文字或语音。"
    _safe_log(db, openid, msg_type or "unknown", "in", xml_string[:1000])
    _safe_log(db, openid, "text", "out", reply_content)
    xml_body = WeChatUtils.build_text_message(to_user=openid, from_user=from_user, content=reply_content)
    return Response(content=xml_body, media_type="application/xml")


async def _handle_event(event: str, openid: str, from_user: str, db: Session):
    if event == WeChatMessageType.SUBSCRIBE:
        reply_content = settings.wechat.welcome_message
        _safe_log(db, openid, "text", "out", reply_content)
        xml_body = WeChatUtils.build_text_message(to_user=openid, from_user=from_user, content=reply_content)
        return Response(content=xml_body, media_type="application/xml")

    if event == WeChatMessageType.UNSUBSCRIBE:
        _safe_log(db, openid, "event", "out", "success")
        return PlainTextResponse(content="success")

    _safe_log(db, openid, "event", "out", "success")
    return PlainTextResponse(content="success")


async def _handle_text(content: str, openid: str, from_user: str, db: Session):
    try:
        message_service = get_message_service(db)
        reply_content, _waiting_confirm = message_service.process_text_message(openid=openid, content=content)
        _safe_log(db, openid, "text", "out", reply_content)
        xml_body = WeChatUtils.build_text_message(to_user=openid, from_user=from_user, content=reply_content)
        return Response(content=xml_body, media_type="application/xml")
    except Exception as exc:
        reply_content = "系统处理出错，请稍后重试。"
        _safe_log(db, openid, "text", "out", reply_content, status="error", error=str(exc))
        xml_body = WeChatUtils.build_text_message(to_user=openid, from_user=from_user, content=reply_content)
        return Response(content=xml_body, media_type="application/xml")
