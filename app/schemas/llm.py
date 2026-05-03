from typing import Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


class WateringParseResult(BaseModel):
    intent: Optional[str] = None
    success: bool = True
    plot_name: Optional[str] = None
    volume: Optional[float] = Field(default=None, gt=0)
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_text(cls, value: Optional[str]) -> Optional[str]:
        if value in (None, ""):
            return None
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("time must be HH:MM")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("time out of range")
        return f"{hour:02d}:{minute:02d}"


def parse_watering_result_json(result_text: str) -> tuple[Optional[WateringParseResult], Optional[str]]:
    try:
        return WateringParseResult.model_validate_json(result_text), None
    except ValidationError as exc:
        return None, str(exc)
