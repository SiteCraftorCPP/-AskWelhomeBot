"""Configuration loader from .env file."""
import os
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

# Get the project root directory (parent of bot/)
project_root = Path(__file__).parent.parent

# Load environment variables from .env file
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)


def _absolute_from_project(p: str) -> str:
    """Путь относительно корня репозитория (для systemd cwd не важен)."""
    p = (p or "").strip()
    if not p:
        return ""
    path = Path(p)
    if path.is_absolute():
        return str(path)
    return str(project_root / path)


def _resolve_report_pdf_path() -> str:
    """Отчёт: env REPORT_PDF_PATH или первый существующий из типовых имён."""
    env = os.getenv("REPORT_PDF_PATH")
    if env:
        return _absolute_from_project(env)
    for rel in (
        "assets/report_2025_msk_spb.pdf",
        "Итоги 2025 Москва-СПб.pdf",
    ):
        p = _absolute_from_project(rel)
        if p and Path(p).is_file():
            return p
    return _absolute_from_project("assets/report_2025_msk_spb.pdf")


def _parse_int_list(value: str) -> list[int]:
    """
    Parse comma-separated list of ints from env (e.g. "1,2,3").
    Silently drops invalid parts and zeros.
    """
    value = (value or "").strip()
    if not value:
        return []
    parts = [p.strip() for p in value.replace(" ", "").split(",") if p.strip()]
    out: list[int] = []
    for p in parts:
        try:
            n = int(p)
        except ValueError:
            continue
        if n != 0:
            out.append(n)
    return out


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = str(raw).strip()
    if raw == "":
        return default
    return int(raw)


def _merge_admin_chat_ids(parsed: list[int], legacy_single: int) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for n in parsed:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    if legacy_single and legacy_single not in seen:
        out.append(legacy_single)
    return out


def _normalize_proxy_url(raw_proxy: str) -> str:
    """
    Нормализует прокси в URL-вид.
    Поддержка:
    - socks5://user:pass@host:port
    - http://user:pass@host:port
    - host:port:user:pass
    """
    raw_proxy = (raw_proxy or "").strip()
    if not raw_proxy:
        return ""
    if "://" in raw_proxy:
        return raw_proxy

    parts = raw_proxy.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"socks5://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return raw_proxy


class Config:
    """Bot configuration."""
    
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    TELEGRAM_PROXY: str = _normalize_proxy_url(os.getenv("TELEGRAM_PROXY", ""))
    # Legacy: ADMIN_CHAT_ID раньше был одним числом.
    # Теперь поддерживаем и "id1,id2" прямо в ADMIN_CHAT_ID.
    _ADMIN_CHAT_ID_RAW: str = os.getenv("ADMIN_CHAT_ID", "")
    _ADMIN_CHAT_ID_LIST_PARSED: list[int] = _parse_int_list(_ADMIN_CHAT_ID_RAW)
    ADMIN_CHAT_ID: int = _ADMIN_CHAT_ID_LIST_PARSED[0] if _ADMIN_CHAT_ID_LIST_PARSED else _get_int("ADMIN_CHAT_ID", 0)

    _ADMIN_CHAT_IDS_PARSED: list[int] = _parse_int_list(os.getenv("ADMIN_CHAT_IDS", ""))
    ADMIN_CHAT_IDS: list[int] = _merge_admin_chat_ids(
        _ADMIN_CHAT_IDS_PARSED + _ADMIN_CHAT_ID_LIST_PARSED,
        ADMIN_CHAT_ID,
    )
    # Список админов через запятую: @user1,@user2 или user1,user2
    ADMIN_USERNAMES: list[str] = [
        u.strip().lstrip("@").lower()
        for u in os.getenv("ADMIN_USERNAMES", "").split(",")
        if u.strip()
    ]
    # Кто может править CORE prompt (если пусто — как обычные админы).
    PROMPT_ADMIN_USERNAMES: list[str] = [
        u.strip().lstrip("@").lower()
        for u in os.getenv("PROMPT_ADMIN_USERNAMES", "").split(",")
        if u.strip()
    ]
    LOGO_PATH: str = _absolute_from_project(os.getenv("LOGO_PATH", "assets/logo.png"))
    REPORT_PDF_PATH: str = _resolve_report_pdf_path()

    # Уведомления в супергруппу с темами (forum): chat_id + message_thread_id из /chatinfo в каждой теме
    FEEDBACK_CHAT_ID: int = _get_int("FEEDBACK_CHAT_ID", 0)
    NOTIFICATION_CHAT_ID: int = _get_int("NOTIFICATION_CHAT_ID", 0) or FEEDBACK_CHAT_ID
    LEADS_TOPIC_ID: int = _get_int("LEADS_TOPIC_ID", 0)
    FEEDBACK_TOPIC_ID: int = _get_int("FEEDBACK_TOPIC_ID", 0)
    
    # ProxyAPI configuration (основной провайдер)
    PROXYAPI_API_KEY: str = os.getenv("PROXYAPI_API_KEY", "")
    PROXYAPI_BASE_URL: str = os.getenv("PROXYAPI_BASE_URL", "https://openai.api.proxyapi.ru/v1")
    PROXYAPI_MODEL: str = os.getenv("PROXYAPI_MODEL", "openai/gpt-5.1")
    PROXYAPI_MAX_TOKENS: int = _get_int("PROXYAPI_MAX_TOKENS", 4000)
    PROXYAPI_TIMEOUT_SECONDS: int = _get_int("PROXYAPI_TIMEOUT_SECONDS", 45)
    
    # OpenRouter configuration (опционально, для отката)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-5.1")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_SITE_URL: str = os.getenv("OPENROUTER_SITE_URL", "http://localhost")
    OPENROUTER_APP_NAME: str = os.getenv("OPENROUTER_APP_NAME", "Welhome Bot")
    OPENROUTER_MAX_TOKENS: int = _get_int("OPENROUTER_MAX_TOKENS", 1500)
    OPENROUTER_TIMEOUT_SECONDS: int = _get_int("OPENROUTER_TIMEOUT_SECONDS", 45)
    
    # LLM Provider selection
    # Определение провайдера по умолчанию:
    # - Если задан PROXYAPI_API_KEY → proxyapi
    # - Если задан OPENROUTER_API_KEY → openrouter
    # - Иначе → proxyapi (по умолчанию)
    _default_provider = "proxyapi"
    if PROXYAPI_API_KEY.strip():
        _default_provider = "proxyapi"
    elif OPENROUTER_API_KEY.strip():
        _default_provider = "openrouter"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", _default_provider).lower()
    
    # Bot Configuration
    BOT_VERSION: str = os.getenv("BOT_VERSION", "1.2.1")
    SESSION_TIMEOUT_MINUTES: int = _get_int("SESSION_TIMEOUT_MINUTES", 60)
    MAX_CONTEXT_MESSAGES: int = _get_int("MAX_CONTEXT_MESSAGES", 50)
    
    # Feature Flags
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
    ENABLE_ESCALATION: bool = os.getenv("ENABLE_ESCALATION", "true").lower() == "true"
    ENABLE_MENU: bool = os.getenv("ENABLE_MENU", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration parameters."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required in .env file")
