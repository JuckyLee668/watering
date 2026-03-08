import os
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.exceptions import LLMException
from app.models.database import SessionLocal
from app.services.llm_service import get_llm_service


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def check_file(path: str, label: str) -> bool:
    if Path(path).exists():
        ok(f"{label}: {path}")
        return True
    fail(f"{label} missing: {path}")
    return False


def check_required_env() -> bool:
    required = {
        "WECHAT_APP_ID": settings.wechat.app_id,
        "WECHAT_APP_SECRET": settings.wechat.app_secret,
        "WECHAT_TOKEN": settings.wechat.token,
        "WECHAT_ENCODING_AES_KEY": settings.wechat.encoding_aes_key,
    }
    missing = [key for key, value in required.items() if not str(value or "").strip()]
    if missing:
        fail(f"missing required WeChat config: {', '.join(missing)}")
        return False
    ok("required WeChat config loaded")
    return True


def check_database() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        ok("database connection ok")
        return True
    except Exception as exc:
        fail(f"database connection failed: {exc}")
        return False
    finally:
        db.close()


def _llm_provider_key_present() -> bool:
    provider = settings.llm.provider
    if provider == "openai":
        return bool(settings.llm.openai.api_key)
    if provider == "zhipuai":
        return bool(settings.llm.zhipuai.api_key)
    if provider == "qwen":
        return bool(settings.llm.qwen.api_key)
    if provider == "deepseek":
        return bool(settings.llm.deepseek.api_key)
    return False


def check_llm() -> bool:
    provider = settings.llm.provider
    if not _llm_provider_key_present():
        fail(f"LLM provider '{provider}' missing API key")
        return False

    try:
        service = get_llm_service()
        if provider in {"openai", "qwen", "deepseek"}:
            model = (
                settings.llm.openai.model if provider == "openai"
                else settings.llm.qwen.model if provider == "qwen"
                else settings.llm.deepseek.model
            )
            service._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                timeout=5,
            )
        elif provider == "zhipuai":
            service._client.chat.completions.create(
                model="glm-4",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                timeout=5,
            )
        else:
            fail(f"unsupported LLM provider: {provider}")
            return False
        ok(f"LLM provider '{provider}' reachable")
        return True
    except LLMException as exc:
        fail(f"LLM init failed: {exc}")
        return False
    except Exception as exc:
        fail(f"LLM request failed: {exc}")
        return False


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Project self-check")
    parser.add_argument("--skip-llm", action="store_true", help="skip LLM connectivity check")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    checks = [
        check_file(root / ".env", ".env"),
        check_file(root / "config.yaml", "config.yaml"),
        check_file(root / settings.plots.csv_path, "plots csv"),
        check_required_env(),
        check_database(),
    ]

    if args.skip_llm:
        print("[SKIP] LLM connectivity check skipped")
    else:
        checks.append(check_llm())

    if all(checks):
        print("[PASS] self-check passed")
        return 0

    print("[FAIL] self-check failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
