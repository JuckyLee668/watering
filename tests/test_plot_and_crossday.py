import sys
from pathlib import Path
from datetime import date, datetime, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.database import Base, Plot
from app.services.llm_service import LLMService
from app.services.message_service import MessageService
from app.services.watering_service import WateringService


def test_plot_match_with_extra_prefix_and_separators():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()
    try:
        db.add(Plot(plot_name="独一独二3-1 50号地", plot_code="PX001", owner_name="林俊杰", status=1))
        db.commit()

        service = WateringService(db)
        service._ensure_plots_from_csv = lambda: None

        matched = service.get_or_create_plot("3-1-50号地")
        assert matched is not None
        assert matched.plot_name == "独一独二3-1 50号地"
        assert matched.owner_name == "林俊杰"
    finally:
        db.close()


def test_local_parser_prefers_enhanced_time_with_period_words():
    service = LLMService.__new__(LLMService)
    current_time = datetime(2026, 3, 8, 10, 0, 0)

    parsed = service._try_parse_local("3-1-50号地 昨天晚上9点到今天中午12点打水59方", current_time)

    assert parsed is not None
    assert parsed["success"] is True
    assert parsed["date"] == "2026-03-07"
    assert parsed["start_time"] == "21:00"
    assert parsed["end_time"] == "12:00"


def test_llm_json_result_time_is_normalized_by_text_context():
    service = LLMService.__new__(LLMService)
    result_text = (
        '{"intent":"watering","confidence":0.9,"plot_name":"3-1-50号地",'
        '"volume":59,"date":"2026-03-07","start_time":"09:00","end_time":"12:00"}'
    )

    parsed = service._parse_json_result(
        result_text=result_text,
        original_input="3-1-50号地 昨天晚上9点到今天中午12点打水59方",
    )

    assert parsed["success"] is True
    assert parsed["start_time"] == "21:00"
    assert parsed["end_time"] == "12:00"


def test_message_time_text_uses_full_datetime_range():
    service = MessageService.__new__(MessageService)
    text = service._build_time_text(date(2026, 3, 6), "21:00", "12:00")
    assert text == "03-06 21:00 - 03-07 12:00"


def test_message_prompt_uses_full_datetime_range():
    service = MessageService.__new__(MessageService)
    pending = {
        "plot_name": "独一独二3-1 50号地",
        "owner_name": "林俊杰",
        "volume": 59,
        "date": "2026-03-06",
        "start_time": "21:00",
        "end_time": "12:00",
    }
    prompt = service._build_confirm_prompt_from_pending(pending)
    assert "时间：03-06 21:00 - 03-07 12:00" in prompt


def test_message_prompt_uses_text_day_span_for_full_datetime_range():
    service = MessageService.__new__(MessageService)
    pending = {
        "plot_name": "独一独二3-1 50号地",
        "owner_name": "林俊杰",
        "volume": 59,
        "date": "2026-03-07",
        "start_time": "09:00",
        "end_time": "12:00",
        "raw_input": "[组长昵称=组长][微信OpenID=o] 3-1-50号地 昨天九点到今天中午12点打水59方",
    }
    prompt = service._build_confirm_prompt_from_pending(pending)
    assert "时间：03-07 09:00 - 03-08 12:00" in prompt


def test_duration_minutes_uses_text_day_span():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()
    try:
        service = WateringService(db)
        service._ensure_plots_from_csv = lambda: None

        record = service.create_watering_record(
            user_id=1,
            plot_id=None,
            plot_name="独一独二3-1 50号地",
            volume=59,
            operation_date=date(2026, 3, 7),
            start_time=time(9, 0),
            end_time=time(12, 0),
            raw_input="[组长昵称=组长][微信OpenID=o] 3-1-50号地 昨天九点到今天中午12点打水59方",
            confirm_status=0,
        )
        assert record.duration_minutes == 27 * 60
    finally:
        db.close()
