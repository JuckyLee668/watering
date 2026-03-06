# -*- coding: utf-8 -*-
"""
核心配置模块
Core Configuration Module

从config.yaml加载配置，提供全局配置访问
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any, List

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用配置"""
    name: str = "微信智能浇水上报系统"
    version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    """数据库配置"""
    driver: str = "mysql+pymysql"
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "watering_db"
    charset: str = "utf8mb4"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True


class RedisConfig(BaseModel):
    """Redis配置"""
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    decode_responses: bool = True
    encoding: str = "utf-8"
    pending_timeout: int = 300
    user_state_ttl: int = 3600


class WeChatConfig(BaseModel):
    """微信配置"""
    app_id: str = ""
    app_secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    callback_url: str = "/wechat/callback"
    welcome_message: str = "您好！欢迎使用智能浇水上报系统。"


class LLMOpenAIConfig(BaseModel):
    """OpenAI配置"""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 500


class LLMZhipuaiConfig(BaseModel):
    """智谱GLM配置"""
    api_key: str = ""


class LLMQwenConfig(BaseModel):
    """通义千问配置"""
    api_key: str = ""
    model: str = "qwen-turbo"


class LLMPromptConfig(BaseModel):
    """LLM Prompt配置"""
    system_template: str = ""
    examples: List[Dict[str, str]] = []


class LLMConfig(BaseModel):
    """大模型配置"""
    provider: str = "zhipuai"
    openai: LLMOpenAIConfig = Field(default_factory=LLMOpenAIConfig)
    zhipuai: LLMZhipuaiConfig = Field(default_factory=LLMZhipuaiConfig)
    qwen: LLMQwenConfig = Field(default_factory=LLMQwenConfig)
    prompt: LLMPromptConfig = Field(default_factory=LLMPromptConfig)




class PlotsConfig(BaseModel):
    """地块配置"""
    enabled: bool = True
    csv_path: str = "data/plots_sample.csv"

class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    format: str = ""
    file: str = "logs/app.log"
    rotation: str = "100 MB"
    retention: str = "30 days"
    compression: str = "zip"


class CORSConfig(BaseModel):
    """CORS配置"""
    enabled: bool = True
    allow_origins: List[str] = ["*"]
    allow_credentials: bool = True
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]


class Settings(BaseModel):
    """全局设置"""

    # 应用配置
    app: AppConfig = Field(default_factory=AppConfig)

    # 数据库配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Redis配置
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # 微信配置
    wechat: WeChatConfig = Field(default_factory=WeChatConfig)

    # 大模型配置
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # 地块配置
    plots: PlotsConfig = Field(default_factory=PlotsConfig)

    # 日志配置
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # CORS配置
    cors: CORSConfig = Field(default_factory=CORSConfig)


def load_config_from_yaml(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    从YAML文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    if config_path is None:
        # 默认配置路径
        config_path = os.environ.get(
            "CONFIG_PATH",
            str(Path(__file__).parent.parent.parent / "config.yaml")
        )

    if not os.path.exists(config_path):
        # 返回默认配置
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    return config_dict or {}


@lru_cache()
def get_settings() -> Settings:
    """
    获取全局配置（单例模式）

    Returns:
        Settings实例
    """
    config_dict = load_config_from_yaml()
    return Settings(**config_dict)


# 全局配置实例
settings = get_settings()
