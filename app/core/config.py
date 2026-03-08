import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "微信智能浇水上报系统"
    version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    url: Optional[str] = None
    driver: str = "mysql+pymysql"
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "watering_db"
    sqlite_path: str = "data/watering.db"
    fallback_to_sqlite: bool = True
    charset: str = "utf8mb4"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True


class StateConfig(BaseModel):
    pending_timeout: int = 300
    user_state_ttl: int = 3600


class WeChatConfig(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    callback_url: str = "/wechat/callback"
    welcome_message: str = "您好！欢迎使用智能浇水上报系统。"


class LLMOpenAIConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 500


class LLMZhipuaiConfig(BaseModel):
    api_key: str = ""


class LLMQwenConfig(BaseModel):
    api_key: str = ""
    model: str = "qwen-turbo"


class LLMDeepSeekConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"


class LLMPromptConfig(BaseModel):
    system_template: str = ""
    examples: List[Dict[str, str]] = Field(default_factory=list)


class LLMConfig(BaseModel):
    provider: str = "zhipuai"
    openai: LLMOpenAIConfig = Field(default_factory=LLMOpenAIConfig)
    zhipuai: LLMZhipuaiConfig = Field(default_factory=LLMZhipuaiConfig)
    qwen: LLMQwenConfig = Field(default_factory=LLMQwenConfig)
    deepseek: LLMDeepSeekConfig = Field(default_factory=LLMDeepSeekConfig)
    prompt: LLMPromptConfig = Field(default_factory=LLMPromptConfig)


class PlotsConfig(BaseModel):
    enabled: bool = True
    csv_path: str = "data/plots_sample.csv"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = ""
    file: str = "logs/app.log"
    rotation: str = "100 MB"
    retention: str = "30 days"
    compression: str = "zip"


class CORSConfig(BaseModel):
    enabled: bool = True
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    wechat: WeChatConfig = Field(default_factory=WeChatConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    plots: PlotsConfig = Field(default_factory=PlotsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def load_dotenv(dotenv_path: Optional[str] = None) -> None:
    if dotenv_path is None:
        dotenv_path = str(Path(__file__).parent.parent.parent / ".env")

    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _resolve_env_value(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2) or ""
        return os.environ.get(key, default)

    return _ENV_PATTERN.sub(repl, value)


def _resolve_env_placeholders(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _resolve_env_placeholders(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_placeholders(v) for v in data]
    if isinstance(data, str):
        return _resolve_env_value(data)
    return data


def load_config_from_yaml(config_path: Optional[str] = None) -> Dict[str, Any]:
    load_dotenv()

    if config_path is None:
        config_path = os.environ.get(
            "CONFIG_PATH",
            str(Path(__file__).parent.parent.parent / "config.yaml"),
        )

    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    return _resolve_env_placeholders(config_dict or {})


def _apply_generic_llm_env(settings: Settings) -> Settings:
    provider = settings.llm.provider
    generic_api_key = os.environ.get("LLM_API_KEY", "").strip()
    generic_base_url = os.environ.get("LLM_BASE_URL", "").strip()
    generic_model = os.environ.get("LLM_MODEL", "").strip()
    generic_temperature = os.environ.get("LLM_TEMPERATURE", "").strip()
    generic_max_tokens = os.environ.get("LLM_MAX_TOKENS", "").strip()

    if provider == "openai":
        if generic_api_key:
            settings.llm.openai.api_key = generic_api_key
        if generic_base_url:
            settings.llm.openai.base_url = generic_base_url
        if generic_model:
            settings.llm.openai.model = generic_model
        if generic_temperature:
            settings.llm.openai.temperature = float(generic_temperature)
        if generic_max_tokens:
            settings.llm.openai.max_tokens = int(generic_max_tokens)
    elif provider == "zhipuai":
        if generic_api_key:
            settings.llm.zhipuai.api_key = generic_api_key
    elif provider == "qwen":
        if generic_api_key:
            settings.llm.qwen.api_key = generic_api_key
        if generic_model:
            settings.llm.qwen.model = generic_model
    elif provider == "deepseek":
        if generic_api_key:
            settings.llm.deepseek.api_key = generic_api_key
        if generic_base_url:
            settings.llm.deepseek.base_url = generic_base_url
        if generic_model:
            settings.llm.deepseek.model = generic_model
        if generic_temperature:
            settings.llm.openai.temperature = float(generic_temperature)
        if generic_max_tokens:
            settings.llm.openai.max_tokens = int(generic_max_tokens)

    return settings


@lru_cache()
def get_settings() -> Settings:
    return _apply_generic_llm_env(Settings(**load_config_from_yaml()))


settings = get_settings()
