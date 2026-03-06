# -*- coding: utf-8 -*-
"""
消息处理服务
Message Processing Service

处理微信消息的核心逻辑
"""

from datetime import datetime, date, time
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session

from app.wechat.utils import WeChatUtils
from app.services.llm_service import get_llm_service
from app.services.redis_service import get_state_manager
from app.services.watering_service import get_watering_service
from app.models.database import User
from app.core.config import settings
from app.core.exceptions import (
    LLMException,
    PendingDataNotFoundException,
    InvalidConfirmationException,
)


class MessageService:
    """消息处理服务"""

    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()
        self.state_manager = get_state_manager()
        self.watering_service = get_watering_service(db)

    def process_text_message(
        self,
        openid: str,
        content: str,
    ) -> Tuple[str, bool]:
        """
        处理用户文本消息

        Args:
            openid: 用户OpenID
            content: 消息内容

        Returns:
            (回复消息, 是否需要等待用户确认)
        """
        # 转换为小写
        content_lower = content.strip().lower()

        # 检查用户是否处于待确认状态
        if self.state_manager.is_waiting_confirm(openid):
            return self._handle_confirmation(openid, content_lower, content)

        # 处理确认指令
        if content_lower in ["1", "确认", "yes", "y", "确定"]:
            # 检查是否有待确认数据
            pending_data = self.state_manager.get_pending_data(openid)
            if pending_data:
                return self._confirm_watering_record(openid, pending_data)
            else:
                return "没有待确认的记录，请重新上报浇水信息。", False

        # 处理取消指令
        if content_lower in ["2", "取消", "no", "n"]:
            # 取消待确认状态
            self.state_manager.delete_pending_data(openid)
            return "已取消本次上报。请重新输入浇水信息。", False

        # 尝试解析浇水信息
        return self._parse_and_confirm(openid, content)

    def _parse_and_confirm(
        self,
        openid: str,
        user_input: str,
    ) -> Tuple[str, bool]:
        """
        解析用户输入并请求确认

        Args:
            openid: 用户OpenID
            user_input: 用户输入

        Returns:
            (回复消息, 是否等待确认)
        """
        try:
            # 调用LLM解析
            parsed = self.llm_service.parse_watering_info(user_input)

            # 检查是否是闲聊
            if parsed.get("is_chat"):
                # 返回欢迎消息
                return settings.wechat.welcome_message, False

            # 检查解析是否成功
            if not parsed.get("success"):
                # 解析失败，返回错误消息
                message = parsed.get("message", "无法理解您输入的内容")
                return f"抱歉，{message}。请按照以下格式输入：\n\n例如：今天下午2点到4点给3号地浇了50方水", False

            # 保存待确认数据
            self.state_manager.save_pending_data(openid, parsed)

            # 构建确认消息
            plot_name = parsed.get("plot_name", "未指定")
            volume = parsed.get("volume", 0)
            date_str = parsed.get("date", datetime.now().strftime("%Y-%m-%d"))
            start_time = parsed.get("start_time")
            end_time = parsed.get("end_time")

            # 格式化时间
            if start_time and end_time:
                time_display = f"{start_time} - {end_time}"
            elif start_time:
                time_display = f"{start_time}开始"
            else:
                time_display = "未指定具体时间"

            confirm_msg = f"""📋 浇水上报确认

地块：{plot_name}
水量：{volume}方
日期：{date_str}
时间：{time_display}

━━━━━━━━━━━━━━━
请回复：
✅ 确认 - 回复"1"或"确认"
❌ 取消 - 回复"2"或"取消"
🔄 修改 - 直接重新上报
━━━━━━━━━━━━━━━

💡 提示：超时5分钟将自动取消"""

            return confirm_msg, True

        except LLMException as e:
            return f"系统错误：{e.message}。请稍后重试。", False

    def _handle_confirmation(
        self,
        openid: str,
        content_lower: str,
        original_content: str,
    ) -> Tuple[str, bool]:
        """
        处理确认流程

        Args:
            openid: 用户OpenID
            content_lower: 小写内容
            original_content: 原始内容

        Returns:
            (回复消息, 是否等待确认)
        """
        # 确认
        if content_lower in ["1", "确认", "yes", "y", "确定"]:
            return self._confirm_watering_record(
                openid,
                self.state_manager.get_pending_data(openid)
            )

        # 取消
        if content_lower in ["2", "取消", "no", "n"]:
            self.state_manager.delete_pending_data(openid)
            return "已取消本次上报。请重新输入浇水信息。", False

        # 修改 - 重新解析
        self.state_manager.delete_pending_data(openid)
        return self._parse_and_confirm(openid, original_content)

    def _confirm_watering_record(
        self,
        openid: str,
        pending_data: Dict[str, Any],
    ) -> Tuple[str, bool]:
        """
        确认并保存浇水记录

        Args:
            openid: 用户OpenID
            pending_data: 待确认数据

        Returns:
            (回复消息, 是否等待确认)
        """
        try:
            # 获取或创建用户
            user = self.watering_service.get_or_create_user(openid)

            # 获取地块ID
            plot_id = None
            plot_name = pending_data.get("plot_name")
            if plot_name:
                plot = self.watering_service.get_or_create_plot(plot_name)
                if plot:
                    plot_id = plot.id
                else:
                    standard_names = self.watering_service.plot_catalog.get_standard_names()[:10]
                    names_text = "、".join(standard_names) if standard_names else "（CSV暂无地块数据）"
                    return (
                        f"未在地块CSV中找到“{plot_name}”。请使用标准地块名称重新上报。\n可用地块：{names_text}",
                        False,
                    )

            # 解析日期
            date_str = pending_data.get("date")
            if date_str:
                operation_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                operation_date = datetime.now().date()

            # 解析时间
            start_time_obj = None
            end_time_obj = None
            start_time_str = pending_data.get("start_time")
            end_time_str = pending_data.get("end_time")

            if start_time_str:
                try:
                    start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
                except ValueError:
                    pass

            if end_time_str:
                try:
                    end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()
                except ValueError:
                    pass

            # 创建浇水记录
            record = self.watering_service.create_watering_record(
                user_id=user.id,
                plot_id=plot_id,
                plot_name=plot_name or "未知地块",
                volume=float(pending_data.get("volume", 0)),
                operation_date=operation_date,
                start_time=start_time_obj,
                end_time=end_time_obj,
                raw_input=pending_data.get("raw_input", ""),
                confirm_status=1,
            )

            # 删除待确认数据
            self.state_manager.delete_pending_data(openid)

            # 返回成功消息
            success_msg = f"""✅ 上报成功！

地块：{plot_name}
水量：{pending_data.get('volume')}方
日期：{operation_date.strftime('%Y年%m月%d日')}
时间：{start_time_str or '未指定'} - {end_time_str or '未指定'}

感谢您的上报！"""

            return success_msg, False

        except Exception as e:
            return f"保存记录失败：{str(e)}。请重新上报。", False

    def get_user_statistics(self, openid: str) -> str:
        """
        获取用户统计信息

        Args:
            openid: 用户OpenID

        Returns:
            统计信息消息
        """
        try:
            # 获取用户
            user = self.watering_service.get_or_create_user(openid)

            # 获取今天的日期范围
            today = datetime.now().date()

            # 获取统计信息
            stats = self.watering_service.get_statistics(
                start_date=today,
                end_date=today,
                user_id=user.id,
            )

            if stats["total_count"] == 0:
                return f"今天暂无浇水记录。"

            return f"""📊 今日统计

浇水次数：{stats['total_count']}次
总浇水量：{stats['total_volume']:.1f}方
平均方数：{stats['avg_volume']:.1f}方"""

        except Exception as e:
            return f"获取统计信息失败：{str(e)}"


# 全局消息服务工厂函数
def get_message_service(db: Session) -> MessageService:
    """获取消息服务实例"""
    return MessageService(db)
