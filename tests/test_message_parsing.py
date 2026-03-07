from datetime import datetime
from types import SimpleNamespace

from app.services.llm_service import LLMService
from app.services.message_service import MessageService


def test_local_parser_supports_full_plot_name_and_cross_day_time():
    service = LLMService.__new__(LLMService)
    current_time = datetime(2026, 3, 7, 10, 0, 0)

    parsed = service._try_parse_local("3-1-50号地 昨天晚上9点到今天中午12点打水59方", current_time)

    assert parsed is not None
    assert parsed["success"] is True
    assert parsed["plot_name"] == "3-1-50号地"
    assert parsed["date"] == "2026-03-06"
    assert parsed["start_time"] == "21:00"
    assert parsed["end_time"] == "12:00"


def test_confirm_message_prefers_standard_plot_full_name():
    class FakeLLMService:
        @staticmethod
        def parse_watering_info(_text):
            return {
                "success": True,
                "plot_name": "50号地",
                "volume": 59,
                "date": "2026-03-06",
                "start_time": "21:00",
                "end_time": "12:00",
                "confidence": 0.95,
            }

    class FakeStateManager:
        def __init__(self):
            self.saved = None

        def save_pending_data(self, _openid, payload):
            self.saved = payload

    class FakeWeChatUserService:
        @staticmethod
        def get_user_nickname(_openid, blocking=False):
            return "测试组长"

    class FakeWateringService:
        @staticmethod
        def get_or_create_user(_openid, name=None):
            return SimpleNamespace(id=1, name=name or "测试组长")

        @staticmethod
        def get_or_create_plot(_plot_name):
            return SimpleNamespace(id=8, plot_name="3-1-50号地", owner_name="林俊杰")

        @staticmethod
        def create_watering_record(**_kwargs):
            return SimpleNamespace(id=1001)

    service = MessageService.__new__(MessageService)
    service.llm_service = FakeLLMService()
    service.state_manager = FakeStateManager()
    service.wechat_user_service = FakeWeChatUserService()
    service.watering_service = FakeWateringService()

    msg, waiting_confirm = service._parse_and_confirm("openid-1", "50号地 昨天晚上9点到今天中午12点打水59方")

    assert waiting_confirm is True
    assert "地块：3-1-50号地" in msg
    assert "农户：林俊杰" in msg
    assert service.state_manager.saved["plot_name"] == "3-1-50号地"
