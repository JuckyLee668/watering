from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import LLMException
from app.services.llm_service import get_llm_service
from app.services.state_service import get_state_manager
from app.services.wechat_user_service import get_wechat_user_service
from app.services.watering_service import get_watering_service


class MessageService:
    """Message processing service for wechat callbacks."""

    CONFIRM_WORDS = {"1", "确认", "yes", "y", "确定"}
    CANCEL_WORDS = {"2", "取消", "no", "n"}

    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()
        self.state_manager = get_state_manager()
        self.wechat_user_service = get_wechat_user_service()
        self.watering_service = get_watering_service(db)

    def process_text_message(self, openid: str, content: str) -> Tuple[str, bool]:
        content = (content or "").strip()
        command = self._normalize_command(content)

        if self.state_manager.is_waiting_confirm(openid):
            return self._handle_confirmation(openid, command, content)

        if command in self.CONFIRM_WORDS:
            pending = self.state_manager.get_pending_data(openid)
            if pending:
                return self._confirm_watering_record(openid, pending)
            return "没有待确认的记录，请先发送浇水信息。", False

        if command in self.CANCEL_WORDS:
            pending = self.state_manager.get_pending_data(openid)
            if pending:
                self._cancel_pending_record(pending)
            self.state_manager.delete_pending_data(openid)
            return "已取消本次上报。", False

        return self._parse_and_confirm(openid, content)

    def _normalize_command(self, content: str) -> str:
        cmd = (content or "").strip().lower()
        cmd = cmd.replace("１", "1").replace("２", "2")
        cmd = cmd.strip("。.!！?？,，；; ")
        return cmd

    def _parse_time(self, t: Optional[str]):
        if not t:
            return None
        try:
            return datetime.strptime(t, "%H:%M").time()
        except ValueError:
            return None

    def _compose_raw_input(self, openid: str, user_name: str, user_input: str) -> str:
        # WeChat callback does not include nickname directly. Use stored leader display name + openid.
        return f"[组长昵称={user_name}][微信OpenID={openid}] {user_input}"

    def _parse_date(self, d: Optional[str]):
        if not d:
            return datetime.now().date()
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            return datetime.now().date()

    def _parse_and_confirm(self, openid: str, user_input: str) -> Tuple[str, bool]:
        try:
            parsed = self.llm_service.parse_watering_info(user_input)

            if parsed.get("is_chat"):
                return settings.wechat.welcome_message, False

            if not parsed.get("success"):
                message = parsed.get("message") or "信息不完整，请补充地块和方量。"
                guide = "示例：今天下午2点到4点给3号地浇了50方水"
                return f"{message}\n{guide}", False

            nickname = self.wechat_user_service.get_user_nickname(openid, blocking=False)
            user = self.watering_service.get_or_create_user(openid, name=nickname)
            raw_input = self._compose_raw_input(openid, user.name, user_input)
            parsed["raw_input"] = raw_input
            plot_name = parsed.get("plot_name")
            plot_id = None
            owner_name = "未登记"
            if plot_name:
                plot = self.watering_service.get_or_create_plot(plot_name)
                if plot:
                    plot_id = plot.id
                    owner_name = plot.owner_name or "未登记"

            operation_date = self._parse_date(parsed.get("date"))
            start_time_obj = self._parse_time(parsed.get("start_time"))
            end_time_obj = self._parse_time(parsed.get("end_time"))

            # Persist as pending first, then update status on confirm/cancel.
            record = self.watering_service.create_watering_record(
                user_id=user.id,
                plot_id=plot_id,
                plot_name=plot_name or "未知地块",
                volume=float(parsed.get("volume", 0) or 0),
                operation_date=operation_date,
                start_time=start_time_obj,
                end_time=end_time_obj,
                raw_input=raw_input,
                confirm_status=0,
            )

            pending_payload = dict(parsed)
            pending_payload["record_id"] = record.id
            pending_payload["owner_name"] = owner_name
            self.state_manager.save_pending_data(openid, pending_payload)

            if parsed.get("start_time") and parsed.get("end_time"):
                time_text = f"{parsed.get('start_time')} - {parsed.get('end_time')}"
            elif parsed.get("start_time"):
                time_text = f"{parsed.get('start_time')} 开始"
            else:
                time_text = "未指定"

            confirm_msg = (
                "请确认浇水记录：\n"
                f"地块：{plot_name or '未指定'}\n"
                f"农户：{owner_name}\n"
                f"水量：{parsed.get('volume', 0)} 方\n"
                f"日期：{operation_date.strftime('%Y-%m-%d')}\n"
                f"时间：{time_text}\n\n"
                "回复 1 或 确认：提交\n"
                "回复 2 或 取消：放弃\n"
                "直接重发内容：修改"
            )
            return confirm_msg, True

        except LLMException:
            return (
                "暂时无法自动解析这条消息，请按标准格式发送。\n"
                "示例：今天下午2点到4点给3号地浇了50方水",
                False,
            )
        except Exception:
            return "消息处理失败，请稍后重试。", False

    def _handle_confirmation(self, openid: str, command: str, original_content: str) -> Tuple[str, bool]:
        pending = self.state_manager.get_pending_data(openid)
        if not pending:
            return "没有待确认的记录，请先发送浇水信息。", False

        if command in self.CONFIRM_WORDS:
            return self._confirm_watering_record(openid, pending)

        if command in self.CANCEL_WORDS:
            self._cancel_pending_record(pending)
            self.state_manager.delete_pending_data(openid)
            return "已取消本次上报。", False

        # Duplicate retry of the same report text: do not cancel/create a new record.
        if self._looks_like_same_pending_input(pending, original_content):
            return self._build_confirm_prompt_from_pending(pending), True

        # User sends a genuinely new report while waiting for confirmation.
        self._cancel_pending_record(pending)
        self.state_manager.delete_pending_data(openid)
        return self._parse_and_confirm(openid, original_content)

    @staticmethod
    def _normalize_free_text(text: str) -> str:
        t = (text or "").strip().lower()
        for ch in [" ", "\t", "\r", "\n", "。", ".", "，", ",", "！", "!", "？", "?", "；", ";", "：", ":"]:
            t = t.replace(ch, "")
        return t

    def _looks_like_same_pending_input(self, pending_data: Dict[str, Any], original_content: str) -> bool:
        raw_input = str(pending_data.get("raw_input") or "")
        # raw_input format: [组长昵称=...][微信OpenID=...] 原始文本
        msg = raw_input.rsplit("] ", 1)[-1] if "] " in raw_input else raw_input
        return self._normalize_free_text(msg) == self._normalize_free_text(original_content)

    def _build_confirm_prompt_from_pending(self, pending_data: Dict[str, Any]) -> str:
        start_time = pending_data.get("start_time")
        end_time = pending_data.get("end_time")
        if start_time and end_time:
            time_text = f"{start_time} - {end_time}"
        elif start_time:
            time_text = f"{start_time} 开始"
        else:
            time_text = "未指定"
        operation_date = self._parse_date(pending_data.get("date"))
        return (
            "请确认浇水记录：\n"
            f"地块：{pending_data.get('plot_name') or '未指定'}\n"
            f"农户：{pending_data.get('owner_name') or '未登记'}\n"
            f"水量：{pending_data.get('volume', 0)} 方\n"
            f"日期：{operation_date.strftime('%Y-%m-%d')}\n"
            f"时间：{time_text}\n\n"
            "回复 1 或 确认：提交\n"
            "回复 2 或 取消：放弃\n"
            "直接重发内容：修改"
        )

    def _cancel_pending_record(self, pending_data: Dict[str, Any]) -> None:
        record_id = pending_data.get("record_id")
        if record_id:
            self.watering_service.update_confirm_status(int(record_id), 2)

    def _create_record_from_pending(self, openid: str, pending_data: Dict[str, Any], confirm_status: int) -> bool:
        """Fallback path when pending has no valid record_id."""
        nickname = self.wechat_user_service.get_user_nickname(openid, blocking=False)
        user = self.watering_service.get_or_create_user(openid, name=nickname)
        plot_id = None
        plot_name = pending_data.get("plot_name")
        if plot_name:
            plot = self.watering_service.get_or_create_plot(plot_name)
            if plot:
                plot_id = plot.id

        operation_date = self._parse_date(pending_data.get("date"))
        start_time_obj = self._parse_time(pending_data.get("start_time"))
        end_time_obj = self._parse_time(pending_data.get("end_time"))

        self.watering_service.create_watering_record(
            user_id=user.id,
            plot_id=plot_id,
            plot_name=plot_name or "未知地块",
            volume=float(pending_data.get("volume", 0) or 0),
            operation_date=operation_date,
            start_time=start_time_obj,
            end_time=end_time_obj,
            raw_input=pending_data.get("raw_input", ""),
            confirm_status=confirm_status,
        )
        return True

    def _confirm_watering_record(self, openid: str, pending_data: Dict[str, Any]) -> Tuple[str, bool]:
        try:
            record_id = pending_data.get("record_id")
            record = None
            if record_id:
                record = self.watering_service.update_confirm_status(int(record_id), 1)

            # Backward compatibility: pending payload created by older code may not carry record_id.
            # Also handles rare cases where pending record is deleted unexpectedly.
            if not record:
                self._create_record_from_pending(openid, pending_data, confirm_status=1)
                operation_date = self._parse_date(pending_data.get("date"))
            else:
                operation_date = record.operation_date

            self.state_manager.delete_pending_data(openid)

            return (
                "上报成功。\n"
                f"地块：{pending_data.get('plot_name') or '未知地块'}\n"
                f"农户：{pending_data.get('owner_name') or '未登记'}\n"
                f"水量：{pending_data.get('volume', 0)} 方\n"
                f"日期：{operation_date.strftime('%Y-%m-%d')}",
                False,
            )
        except Exception as exc:
            return f"保存失败：{str(exc)}", False

    def get_user_statistics(self, openid: str) -> str:
        try:
            user = self.watering_service.get_or_create_user(openid)
            today = datetime.now().date()
            stats = self.watering_service.get_statistics(
                start_date=today,
                end_date=today,
                user_id=user.id,
            )
            if stats["total_count"] == 0:
                return "今天暂无浇水记录。"
            return (
                "今日统计\n"
                f"浇水次数：{stats['total_count']}\n"
                f"总方量：{stats['total_volume']:.1f} 方\n"
                f"平均方量：{stats['avg_volume']:.1f} 方"
            )
        except Exception as exc:
            return f"统计查询失败：{str(exc)}"


def get_message_service(db: Session) -> MessageService:
    return MessageService(db)

