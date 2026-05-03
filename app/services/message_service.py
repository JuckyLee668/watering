import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import LLMException
from app.services.llm_service import get_llm_service
from app.services.state_service import get_state_manager
from app.services.wechat_user_service import get_wechat_user_service
from app.services.watering_service import get_watering_service


class MessageService:
    """Message processing service for WeChat callbacks."""

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
        return cmd.strip("。.!！?？,，;；:： ")

    @staticmethod
    def _parse_time(t: Optional[str]):
        if not t:
            return None
        try:
            return datetime.strptime(t, "%H:%M").time()
        except ValueError:
            return None

    @staticmethod
    def _parse_date(d: Optional[str]) -> date:
        if not d:
            return datetime.now().date()
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            return datetime.now().date()

    @staticmethod
    def _compose_raw_input(openid: str, user_name: str, user_input: str) -> str:
        return f"[组长昵称={user_name}][微信OpenID={openid}] {user_input}"

    @staticmethod
    def _extract_original_text(raw_input: Optional[str]) -> str:
        text = str(raw_input or "")
        return text.rsplit("] ", 1)[-1] if "] " in text else text

    @staticmethod
    def _relative_day_value(day_word: Optional[str]) -> Optional[int]:
        mapping = {
            "前天": -2,
            "昨天": -1,
            "今天": 0,
            "明天": 1,
            "次日": 1,
            "翌日": 1,
            "第二天": 1,
        }
        return mapping.get(day_word) if day_word else None

    @classmethod
    def _infer_end_date(
        cls,
        operation_date: date,
        start_time: Optional[str],
        end_time: Optional[str],
        raw_input: Optional[str] = None,
    ) -> date:
        start_obj = cls._parse_time(start_time)
        end_obj = cls._parse_time(end_time)
        if start_obj and end_obj and end_obj < start_obj:
            return operation_date + timedelta(days=1)

        text = cls._extract_original_text(raw_input)
        day_span = re.search(
            r"(前天|昨天|今天|明天).{0,20}?(?:到|至|~|～|—|–|-).{0,20}?(昨天|今天|明天|次日|翌日|第二天)",
            text,
        )
        if not day_span:
            return operation_date

        start_day = cls._relative_day_value(day_span.group(1))
        end_day = cls._relative_day_value(day_span.group(2))
        if start_day is None or end_day is None or end_day <= start_day:
            return operation_date
        return operation_date + timedelta(days=end_day - start_day)

    @classmethod
    def _build_time_text(
        cls,
        operation_date: date,
        start_time: Optional[str],
        end_time: Optional[str],
        raw_input: Optional[str] = None,
    ) -> str:
        if start_time and end_time:
            if not cls._parse_time(start_time) or not cls._parse_time(end_time):
                return f"{start_time} - {end_time}"
            end_date = cls._infer_end_date(operation_date, start_time, end_time, raw_input=raw_input)
            return f"{operation_date:%m-%d} {start_time} - {end_date:%m-%d} {end_time}"
        if start_time:
            return f"{operation_date:%m-%d} {start_time}"
        return "未指定"

    def _parse_and_confirm(self, openid: str, user_input: str) -> Tuple[str, bool]:
        try:
            parsed = self.llm_service.parse_watering_info(user_input)
            if parsed.get("is_chat"):
                return settings.wechat.welcome_message, False
            if not parsed.get("success"):
                message = parsed.get("message") or "信息不完整，请补充地块和方量。"
                return f"{message}\n示例：今天下午2点到4点给3号地浇了50方水", False

            nickname = self.wechat_user_service.get_user_nickname(openid, blocking=False)
            user = self.watering_service.get_or_create_user(openid, name=nickname)
            raw_input = self._compose_raw_input(openid, user.name, user_input)
            parsed["raw_input"] = raw_input

            parsed_plot_name = parsed.get("plot_name")
            display_plot_name = parsed_plot_name
            plot_id = None
            owner_name = "未登记"
            if parsed_plot_name:
                plot = self.watering_service.get_or_create_plot(parsed_plot_name)
                if plot:
                    plot_id = plot.id
                    display_plot_name = plot.plot_name or parsed_plot_name
                    owner_name = plot.owner_name or "未登记"

            operation_date = self._parse_date(parsed.get("date"))
            record = self.watering_service.create_watering_record(
                user_id=user.id,
                plot_id=plot_id,
                plot_name=display_plot_name or "未知地块",
                volume=float(parsed.get("volume", 0) or 0),
                operation_date=operation_date,
                start_time=self._parse_time(parsed.get("start_time")),
                end_time=self._parse_time(parsed.get("end_time")),
                raw_input=raw_input,
                confirm_status=0,
            )

            pending_payload = dict(parsed)
            pending_payload["plot_name"] = display_plot_name
            pending_payload["record_id"] = record.id
            pending_payload["owner_name"] = owner_name
            self.state_manager.save_pending_data(openid, pending_payload)

            time_text = self._build_time_text(
                operation_date,
                parsed.get("start_time"),
                parsed.get("end_time"),
                raw_input=raw_input,
            )
            return self._build_confirm_message(display_plot_name, owner_name, parsed.get("volume", 0), operation_date, time_text), True
        except LLMException:
            return "暂时无法自动解析这条消息，请按标准格式发送。\n示例：今天下午2点到4点给3号地浇了50方水", False
        except Exception:
            return "消息处理失败，请稍后重试。", False

    @staticmethod
    def _build_confirm_message(
        plot_name: Optional[str],
        owner_name: str,
        volume: Any,
        operation_date: date,
        time_text: str,
    ) -> str:
        return (
            "请确认浇水记录：\n"
            f"地块：{plot_name or '未指定'}\n"
            f"农户：{owner_name}\n"
            f"水量：{volume} 方\n"
            f"日期：{operation_date:%Y-%m-%d}\n"
            f"时间：{time_text}\n\n"
            "回复 1 或 确认：提交\n"
            "回复 2 或 取消：放弃\n"
            "直接重发内容：修改"
        )

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

        if self._looks_like_same_pending_input(pending, original_content):
            return self._build_confirm_prompt_from_pending(pending), True

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
        msg = self._extract_original_text(pending_data.get("raw_input"))
        return self._normalize_free_text(msg) == self._normalize_free_text(original_content)

    def _build_confirm_prompt_from_pending(self, pending_data: Dict[str, Any]) -> str:
        operation_date = self._parse_date(pending_data.get("date"))
        time_text = self._build_time_text(
            operation_date,
            pending_data.get("start_time"),
            pending_data.get("end_time"),
            raw_input=pending_data.get("raw_input"),
        )
        return self._build_confirm_message(
            pending_data.get("plot_name"),
            pending_data.get("owner_name") or "未登记",
            pending_data.get("volume", 0),
            operation_date,
            time_text,
        )

    def _cancel_pending_record(self, pending_data: Dict[str, Any]) -> None:
        record_id = pending_data.get("record_id")
        if record_id:
            self.watering_service.update_confirm_status(int(record_id), 2, expected_status=0)

    def _create_record_from_pending(self, openid: str, pending_data: Dict[str, Any], confirm_status: int) -> bool:
        nickname = self.wechat_user_service.get_user_nickname(openid, blocking=False)
        user = self.watering_service.get_or_create_user(openid, name=nickname)
        plot_id = None
        plot_name = pending_data.get("plot_name")
        if plot_name:
            plot = self.watering_service.get_or_create_plot(plot_name)
            if plot:
                plot_id = plot.id

        self.watering_service.create_watering_record(
            user_id=user.id,
            plot_id=plot_id,
            plot_name=plot_name or "未知地块",
            volume=float(pending_data.get("volume", 0) or 0),
            operation_date=self._parse_date(pending_data.get("date")),
            start_time=self._parse_time(pending_data.get("start_time")),
            end_time=self._parse_time(pending_data.get("end_time")),
            raw_input=pending_data.get("raw_input", ""),
            confirm_status=confirm_status,
        )
        return True

    def _confirm_watering_record(self, openid: str, pending_data: Dict[str, Any]) -> Tuple[str, bool]:
        try:
            record_id = pending_data.get("record_id")
            record = (
                self.watering_service.update_confirm_status(int(record_id), 1, expected_status=0)
                if record_id
                else None
            )
            operation_date = record.operation_date if record else self._parse_date(pending_data.get("date"))
            if not record:
                self._create_record_from_pending(openid, pending_data, confirm_status=1)

            self.state_manager.delete_pending_data(openid)
            return (
                "上报成功。\n"
                f"地块：{pending_data.get('plot_name') or '未知地块'}\n"
                f"农户：{pending_data.get('owner_name') or '未登记'}\n"
                f"水量：{pending_data.get('volume', 0)} 方\n"
                f"日期：{operation_date:%Y-%m-%d}",
                False,
            )
        except Exception as exc:
            return f"保存失败：{str(exc)}", False

    def get_user_statistics(self, openid: str) -> str:
        try:
            user = self.watering_service.get_or_create_user(openid)
            today = datetime.now().date()
            stats = self.watering_service.get_statistics(start_date=today, end_date=today, user_id=user.id)
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
