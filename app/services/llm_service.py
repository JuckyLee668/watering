import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.exceptions import LLMException


class LLMService:
    """LLM parsing service for watering messages."""

    def __init__(self):
        self._provider = settings.llm.provider
        self._client = None
        self._init_client()

    def _init_client(self):
        if self._provider == "openai":
            self._init_openai()
        elif self._provider == "zhipuai":
            self._init_zhipuai()
        elif self._provider == "qwen":
            self._init_qwen()
        elif self._provider == "deepseek":
            self._init_deepseek()
        else:
            raise LLMException(f"unsupported llm provider: {self._provider}")

    def _init_openai(self):
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.openai.api_key,
                base_url=settings.llm.openai.base_url,
            )
        except ImportError as exc:
            raise LLMException("please install openai: pip install openai") from exc

    def _init_zhipuai(self):
        try:
            from zhipuai import ZhipuAI

            self._client = ZhipuAI(api_key=settings.llm.zhipuai.api_key)
        except ImportError as exc:
            raise LLMException("please install zhipuai: pip install zhipuai") from exc

    def _init_qwen(self):
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.qwen.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        except ImportError as exc:
            raise LLMException("please install openai: pip install openai") from exc

    def _init_deepseek(self):
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.deepseek.api_key,
                base_url=settings.llm.deepseek.base_url,
            )
        except ImportError as exc:
            raise LLMException("please install openai: pip install openai") from exc

    def parse_watering_info(
        self,
        user_input: str,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if current_time is None:
            current_time = datetime.now()

        if not self.is_watering_request(user_input):
            return {
                "success": False,
                "is_chat": True,
                "raw_input": user_input,
            }

        local_parsed = self._try_parse_local(user_input, current_time)
        if local_parsed is not None:
            return local_parsed

        prompt = self._build_prompt(user_input, current_time)

        try:
            if self._provider in ("openai", "qwen", "deepseek"):
                if self._provider == "openai":
                    model = settings.llm.openai.model
                elif self._provider == "qwen":
                    model = settings.llm.qwen.model
                else:
                    model = settings.llm.deepseek.model

                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=settings.llm.openai.temperature,
                    max_tokens=settings.llm.openai.max_tokens,
                    timeout=3.5,
                )
                result_text = response.choices[0].message.content

            elif self._provider == "zhipuai":
                response = self._client.chat.completions.create(
                    model="glm-4",
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=settings.llm.openai.temperature,
                    timeout=3.5,
                )
                result_text = response.choices[0].message.content

            else:
                raise LLMException(f"unsupported provider: {self._provider}")

            return self._parse_json_result(result_text, user_input)

        except Exception as exc:
            raise LLMException(f"llm call failed: {str(exc)}") from exc

    def _build_prompt(self, user_input: str, current_time: datetime) -> Dict[str, str]:
        current_datetime_str = current_time.strftime("%Y-%m-%d %H:%M")
        today_date = current_time.strftime("%Y-%m-%d")

        system_prompt = settings.llm.prompt.system_template.format(
            current_datetime=current_datetime_str
        )

        examples = settings.llm.prompt.examples or []
        few_shot_parts = []
        for index, example in enumerate(examples, start=1):
            output = (example.get("output") or "").replace("{today_date}", today_date)
            few_shot_parts.append(
                f"Example {index}:\\n"
                f"Input: {example.get('input', '')}\\n"
                f"Output: {output}"
            )

        few_shot_text = "\\n\\n".join(few_shot_parts)

        user_prompt = (
            "Please extract structured watering info from the user message.\\n\\n"
            f"Current date: {today_date}\\n\\n"
            f"{few_shot_text}\\n\\n"
            f"User message: {user_input}\\n\\n"
            "Return JSON only."
        )

        return {"system": system_prompt, "user": user_prompt}

    def _parse_json_result(self, result_text: str, original_input: str) -> Dict[str, Any]:
        try:
            result_text = (result_text or "").strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            data = json.loads(result_text)

            if data.get("intent") == "chat":
                return {
                    "success": False,
                    "is_chat": True,
                    "raw_input": original_input,
                }

            if data.get("confidence", 0) < 0.5:
                return {
                    "success": False,
                    "confidence": data.get("confidence", 0),
                    "raw_input": original_input,
                    "message": "信息不完整或无法理解",
                }

            return {
                "success": True,
                "plot_name": data.get("plot_name"),
                "volume": data.get("volume"),
                "date": data.get("date"),
                "start_time": data.get("start_time"),
                "end_time": data.get("end_time"),
                "confidence": data.get("confidence", 0),
                "raw_input": original_input,
            }

        except json.JSONDecodeError as exc:
            return {
                "success": False,
                "raw_input": original_input,
                "message": f"解析失败: {str(exc)}",
            }

    def _try_parse_local(self, user_input: str, current_time: datetime) -> Optional[Dict[str, Any]]:
        text = (user_input or "").strip()
        if not text:
            return None

        volume_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:方|立方|m3|m³)", text, re.IGNORECASE)
        if not volume_match:
            return None
        volume = float(volume_match.group(1))

        plot_match = re.search(r"((?:\d+|[一二两三四五六七八九十]+)\s*号地)", text)
        if not plot_match:
            return None
        plot_name = self._normalize_plot_name(plot_match.group(1).replace(" ", ""))

        operation_date = current_time.date()
        if "昨天" in text:
            operation_date = operation_date - timedelta(days=1)
        elif "前天" in text:
            operation_date = operation_date - timedelta(days=2)

        start_time = None
        end_time = None
        time_range = re.search(
            r"([0-9一二两三四五六七八九十]{1,3})(?:[:点时](\d{1,2}|半)?)?\s*(?:到|至|-)\s*([0-9一二两三四五六七八九十]{1,3})(?:[:点时](\d{1,2}|半)?)?",
            text,
        )
        if time_range:
            h1 = self._parse_hour_token(time_range.group(1))
            h2 = self._parse_hour_token(time_range.group(3))
            m1 = self._parse_minute_token(time_range.group(2))
            m2 = self._parse_minute_token(time_range.group(4))
            if h1 is not None and h2 is not None and m1 is not None and m2 is not None and 0 <= h1 <= 23 and 0 <= h2 <= 23 and 0 <= m1 <= 59 and 0 <= m2 <= 59:
                start_time = f"{h1:02d}:{m1:02d}"
                end_time = f"{h2:02d}:{m2:02d}"

        return {
            "success": True,
            "plot_name": plot_name,
            "volume": volume,
            "date": operation_date.isoformat(),
            "start_time": start_time,
            "end_time": end_time,
            "confidence": 0.95,
            "raw_input": user_input,
        }

    @staticmethod
    def _cn_to_int(text: str) -> Optional[int]:
        digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if not text:
            return None
        if text.isdigit():
            return int(text)
        if text in digits:
            return digits[text]
        if text == "十":
            return 10
        if "十" in text:
            parts = text.split("十")
            tens = digits.get(parts[0], 1) if parts[0] else 1
            ones = digits.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            return tens * 10 + ones
        return None

    def _parse_hour_token(self, token: Optional[str]) -> Optional[int]:
        if not token:
            return None
        return self._cn_to_int(token.strip())

    @staticmethod
    def _parse_minute_token(token: Optional[str]) -> Optional[int]:
        if token is None or token == "":
            return 0
        t = token.strip()
        if t == "半":
            return 30
        if t.isdigit():
            return int(t)
        return None

    def _normalize_plot_name(self, plot_name: str) -> str:
        if plot_name.endswith("号地"):
            prefix = plot_name[:-2]
            n = self._cn_to_int(prefix)
            if n is not None:
                return f"{n}号地"
        return plot_name

    def is_watering_request(self, user_input: str) -> bool:
        keywords = [
            "浇水",
            "灌水",
            "灌溉",
            "方",
            "立方",
            "号地",
            "地块",
            "田",
        ]
        return any(keyword in user_input for keyword in keywords)


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
