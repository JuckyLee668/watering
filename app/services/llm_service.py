# -*- coding: utf-8 -*-
"""
大模型解析服务
LLM Parsing Service

使用大模型从自然语言中提取浇水信息
"""

import json
import re
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.exceptions import LLMException


class LLMService:
    """大模型服务类"""

    def __init__(self):
        self._provider = settings.llm.provider
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化大模型客户端"""
        if self._provider == "openai":
            self._init_openai()
        elif self._provider == "zhipuai":
            self._init_zhipuai()
        elif self._provider == "qwen":
            self._init_qwen()
        else:
            raise LLMException(f"不支持的大模型提供商: {self._provider}")

    def _init_openai(self):
        """初始化OpenAI客户端"""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.llm.openai.api_key,
                base_url=settings.llm.openai.base_url,
            )
        except ImportError:
            raise LLMException("请安装openai库: pip install openai")

    def _init_zhipuai(self):
        """初始化智谱GLM客户端"""
        try:
            from zhipuai import ZhipuAI
            self._client = ZhipuAI(api_key=settings.llm.zhipuai.api_key)
        except ImportError:
            raise LLMException("请安装zhipuai库: pip install zhipuai")

    def _init_qwen(self):
        """初始化通义千问客户端"""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.llm.qwen.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        except ImportError:
            raise LLMException("请安装openai库: pip install openai")

    def parse_watering_info(
        self,
        user_input: str,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        解析浇水信息

        Args:
            user_input: 用户输入的自然语言
            current_time: 当前时间

        Returns:
            解析结果字典
        """
        if current_time is None:
            current_time = datetime.now()

        # 构建Prompt
        prompt = self._build_prompt(user_input, current_time)

        # 调用大模型
        try:
            if self._provider == "openai" or self._provider == "qwen":
                response = self._client.chat.completions.create(
                    model=settings.llm.openai.model if self._provider == "openai" else settings.llm.qwen.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=settings.llm.openai.temperature,
                    max_tokens=settings.llm.openai.max_tokens,
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
                )
                result_text = response.choices[0].message.content

            else:
                raise LLMException(f"不支持的提供商: {self._provider}")

            # 解析JSON结果
            return self._parse_json_result(result_text, user_input)

        except Exception as e:
            raise LLMException(f"大模型调用失败: {str(e)}")

    def _build_prompt(
        self,
        user_input: str,
        current_time: datetime,
    ) -> Dict[str, str]:
        """构建Prompt"""

        # 格式化当前时间
        current_datetime_str = current_time.strftime("%Y年%m月%d日 %H:%M")

        # 系统提示词
        system_prompt = settings.llm.prompt.system_template.format(
            current_datetime=current_datetime_str
        )

        # 用户提示词
        user_prompt = f"""请从以下用户输入中提取浇水信息：

用户输入：{user_input}

请直接输出JSON格式的解析结果，不要添加任何解释。"""

        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def _parse_json_result(
        self,
        result_text: str,
        original_input: str,
    ) -> Dict[str, Any]:
        """
        解析大模型返回的JSON结果

        Args:
            result_text: 大模型返回的文本
            original_input: 用户原始输入

        Returns:
            解析后的字典
        """
        # 尝试提取JSON
        try:
            # 去除可能的markdown代码块标记
            result_text = result_text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            # 解析JSON
            data = json.loads(result_text)

            # 检查是否是闲聊
            if data.get("intent") == "chat":
                return {
                    "success": False,
                    "is_chat": True,
                    "raw_input": original_input,
                }

            # 验证必要字段
            if data.get("confidence", 0) < 0.5:
                return {
                    "success": False,
                    "confidence": data.get("confidence", 0),
                    "raw_input": original_input,
                    "message": "信息不完整或无法理解",
                }

            # 构建返回数据
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

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "raw_input": original_input,
                "message": f"解析失败: {str(e)}",
            }

    def is_watering_request(self, user_input: str) -> bool:
        """
        快速判断是否是浇水上报请求

        Args:
            user_input: 用户输入

        Returns:
            是否可能是浇水请求
        """
        # 关键词匹配
        keywords = [
            "浇水", "灌水", "浇地", "灌溉",
            "方", "立方米",
            "号地", "地块", "田",
        ]

        input_lower = user_input.lower()
        return any(keyword in input_lower for keyword in keywords)


# 全局LLM服务实例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取LLM服务实例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
