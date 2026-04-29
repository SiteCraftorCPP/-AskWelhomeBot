"""LLM integration with ProxyAPI and OpenRouter."""
import logging
import asyncio
import httpx
from openai import AsyncOpenAI
from openai import PermissionDeniedError, APIError
from bot.config import Config
from bot.errors import APITimeoutError, RateLimitError, InvalidInputError

logger = logging.getLogger(__name__)


def _build_openai_http_client(timeout_seconds: int) -> httpx.AsyncClient:
    kwargs: dict = {
        "timeout": httpx.Timeout(timeout=float(timeout_seconds)),
    }
    if Config.TELEGRAM_PROXY:
        kwargs["proxy"] = Config.TELEGRAM_PROXY
    return httpx.AsyncClient(**kwargs)

# Initialize ProxyAPI client
proxyapi_key_initial = Config.PROXYAPI_API_KEY.strip() if Config.PROXYAPI_API_KEY else ""
proxyapi_client = None
if proxyapi_key_initial:
    proxyapi_client = AsyncOpenAI(
        api_key=proxyapi_key_initial,
        base_url=Config.PROXYAPI_BASE_URL,
        timeout=Config.PROXYAPI_TIMEOUT_SECONDS,
        http_client=_build_openai_http_client(Config.PROXYAPI_TIMEOUT_SECONDS),
    )
    logger.info(f"ProxyAPI клиент инициализирован (модель: {Config.PROXYAPI_MODEL})")

# Initialize OpenAI client for OpenRouter
# Initialize even if not selected as primary provider (for fallback)
openrouter_key_initial = Config.OPENROUTER_API_KEY.strip() if Config.OPENROUTER_API_KEY else ""
openrouter_client = None
if openrouter_key_initial:
    openrouter_client = AsyncOpenAI(
        api_key=openrouter_key_initial,
        base_url=Config.OPENROUTER_BASE_URL,
        timeout=Config.OPENROUTER_TIMEOUT_SECONDS,
        http_client=_build_openai_http_client(Config.OPENROUTER_TIMEOUT_SECONDS),
        default_headers={
            "HTTP-Referer": Config.OPENROUTER_SITE_URL,
            "X-Title": Config.OPENROUTER_APP_NAME,
        }
    )
    logger.info(f"OpenRouter клиент инициализирован (модель: {Config.OPENROUTER_MODEL})")

FALLBACK_MESSAGE = "Сервис временно недоступен, попробуйте позже."

# Всегда дописываем: модель любит «рисовать» несуществующие кнопки в квадратных скобках.
_TELEGRAM_UI_RULE = (
    "\n\n"
    "ИНТЕРФЕЙС TELEGRAM (обязательно):\n"
    "- Запрещено имитировать кнопки текстом в квадратных скобках: [Связаться…], [Подключить специалиста] и любые […] как «кнопки».\n"
    "- Если уместна связь со специалистом: дай полезный ответ и 1–2 коротких уточняющих вопроса по делу; не пиши «нажмите кнопку» — реальная inline-кнопка показывается ботом отдельно.\n"
    "- Не дублируй призывы «нажмите кнопку ниже».\n"
    "- Брендинг: используй только название «Welhome». Никогда не упоминай «FB ActiveGroup» или другие бренды."
)

# Окно истории в chat completion (сообщения U + B)
CHAT_HISTORY_MAX_MESSAGES = 12
_CHAT_USER_MAX_LEN = 2000
_CHAT_ASSISTANT_MAX_LEN = 6000


def _build_openai_messages(
    system_prompt: str,
    section: str | None,
    conversation_history: list[dict] | None,
    fallback_user_text: str,
) -> list[dict]:
    """
    system + последние N реплик (U -> user, B -> assistant).
    У последнего сообщения пользователя добавляем выбранный раздел (текущий ход).
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    section_text = section if section else "не выбран"
    hist = list(conversation_history or [])
    hist = hist[-CHAT_HISTORY_MAX_MESSAGES:]

    if not hist:
        u = (fallback_user_text or "")[:_CHAT_USER_MAX_LEN]
        messages.append(
            {
                "role": "user",
                "content": f"Выбранный раздел: {section_text}\n\nВопрос пользователя:\n{u}",
            }
        )
        return messages

    last_u_idx = -1
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("role") == "U":
            last_u_idx = i
            break

    for i, item in enumerate(hist):
        role = item.get("role")
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if role == "U":
            if i == last_u_idx:
                content = (
                    f"Выбранный раздел: {section_text}\n\nВопрос пользователя:\n"
                    f"{text[:_CHAT_USER_MAX_LEN]}"
                )
            else:
                content = text[:_CHAT_USER_MAX_LEN]
            messages.append({"role": "user", "content": content})
        elif role == "B":
            messages.append(
                {"role": "assistant", "content": text[:_CHAT_ASSISTANT_MAX_LEN]}
            )
    return messages


def build_system_prompt(context: dict | None = None) -> str:
    """
    Построить системный промпт с учетом контекста сессии.
    
    Args:
        context: Контекст сессии с asked_questions и collected_data
        
    Returns:
        Системный промпт с добавленным контекстом
    """
    from bot.prompt_store import get_core_prompt
    base_prompt = get_core_prompt()
    
    if not context:
        return base_prompt + _TELEGRAM_UI_RULE
    
    context_addition = ""
    
    # Добавление информации о уже заданных вопросах
    asked_questions = context.get("asked_questions", [])
    if asked_questions:
        questions_str = ", ".join(asked_questions)
        context_addition += f"\n\nКОНТЕКСТ СЕССИИ:\n"
        context_addition += f"Уже заданные вопросы: {questions_str}\n"
        context_addition += f"НЕ задавай эти вопросы повторно, если данные уже известны.\n"
    
    # Добавление информации о собранных данных
    collected_data = context.get("collected_data", {})
    if collected_data and any(collected_data.values()):
        context_addition += f"\nИзвестная информация о пользователе:\n"
        import json
        # Фильтруем пустые значения для читаемости
        filtered_data = {k: v for k, v in collected_data.items() if v}
        if filtered_data:
            context_addition += json.dumps(filtered_data, ensure_ascii=False, indent=2)
            context_addition += f"\nИспользуй эту информацию в своих ответах.\n"

    ch = context.get("conversation_history") or []
    if isinstance(ch, list) and len(ch) > 0:
        context_addition += (
            "\n\nДИАЛОГ: в запрос передаётся история переписки (пользователь и ассистент). "
            "Учитывай уже названные параметры объекта/сделки (город, ЖК, площадь, бюджет и т.д.) "
            "и не переспрашивай их без необходимости."
        )

    return base_prompt + context_addition + _TELEGRAM_UI_RULE


async def generate_reply(
    user_text: str,
    section: str | None,
    session_data: dict | None = None
) -> str:
    """
    Generate reply using ProxyAPI or OpenRouter LLM.
    
    Args:
        user_text: User's question text
        section: Selected section name or None
        session_data: Optional session data with context (city, property_type, request_type, budget, urgency)
        
    Returns:
        Generated reply or fallback message
    """
    # Check if API is configured for selected provider
    has_api = False
    if Config.LLM_PROVIDER == "proxyapi":
        has_api = bool(Config.PROXYAPI_API_KEY and Config.PROXYAPI_API_KEY.strip())
        if not has_api:
            logger.warning("LLM_PROVIDER=proxyapi, но PROXYAPI_API_KEY не задан")
    elif Config.LLM_PROVIDER == "openrouter":
        has_api = bool(Config.OPENROUTER_API_KEY and Config.OPENROUTER_API_KEY.strip())
        if not has_api:
            logger.warning("LLM_PROVIDER=openrouter, но OPENROUTER_API_KEY не задан")
    else:
        logger.warning(f"Неизвестный LLM_PROVIDER: {Config.LLM_PROVIDER}, используем fallback")
    
    if not has_api:
        logger.warning("No LLM API keys configured for selected provider, returning fallback")
        return FALLBACK_MESSAGE
    
    # Log provider and model
    if Config.LLM_PROVIDER == "proxyapi":
        logger.info(f"Провайдер: ProxyAPI, модель: {Config.PROXYAPI_MODEL}")
    elif Config.LLM_PROVIDER == "openrouter":
        logger.info(f"Провайдер: OpenRouter, модель: {Config.OPENROUTER_MODEL}")
    
    # Build context from session_data (for backward compatibility)
    # session_data может содержать как старый формат (плоский dict), так и новый (с collected_data и asked_questions)
    context = {}
    if session_data:
        # Если session_data содержит новый формат (collected_data, asked_questions)
        if "collected_data" in session_data:
            context = session_data
        else:
            # Старый формат - преобразуем в новый
            context = {
                "collected_data": {},
                "asked_questions": session_data.get("asked_questions", []),
                "conversation_history": session_data.get("conversation_history", []),
            }
            # Переносим поля в collected_data
            if session_data.get("city"):
                context["collected_data"]["location"] = {"city": session_data["city"]}
            if session_data.get("property_type"):
                context["collected_data"]["object_type"] = session_data["property_type"]
            if session_data.get("request_type"):
                context["collected_data"]["request_type"] = session_data["request_type"]
            elif session_data.get("goal"):
                context["collected_data"]["request_type"] = session_data["goal"]
            if session_data.get("budget"):
                context["collected_data"]["budget"] = session_data["budget"]
            if session_data.get("urgency"):
                context["collected_data"]["urgency"] = session_data["urgency"]
    
    # Build system prompt with context
    system_prompt = build_system_prompt(context if context else None)

    conv_hist: list[dict] = []
    if session_data:
        conv_hist = session_data.get("conversation_history") or []
    api_messages = _build_openai_messages(
        system_prompt,
        section,
        conv_hist,
        user_text,
    )
    
    # Flag to track if we should try OpenRouter as fallback after ProxyAPI error
    try_openrouter_fallback = False
    
    # Try ProxyAPI first (if configured and selected)
    if proxyapi_client and Config.LLM_PROVIDER == "proxyapi":
        logger.info(f"Использую ProxyAPI (модель: {Config.PROXYAPI_MODEL})")
        try:
            # Для некоторых моделей ProxyAPI (например, gpt-5-mini):
            # - нужно использовать max_completion_tokens вместо max_tokens
            # - temperature не поддерживается (только значение по умолчанию 1)
            response = await proxyapi_client.chat.completions.create(
                model=Config.PROXYAPI_MODEL,
                messages=api_messages,
                max_completion_tokens=Config.PROXYAPI_MAX_TOKENS
            )
            
            # Детальное логирование ответа для отладки
            logger.info(f"ProxyAPI response type: {type(response)}")
            logger.info(f"ProxyAPI response.choices exists: {hasattr(response, 'choices')}")
            if hasattr(response, 'choices'):
                logger.info(f"ProxyAPI response.choices: {response.choices}")
                logger.info(f"ProxyAPI response.choices length: {len(response.choices) if response.choices else 0}")
                if response.choices and len(response.choices) > 0:
                    logger.info(f"ProxyAPI response.choices[0] type: {type(response.choices[0])}")
                    logger.info(f"ProxyAPI response.choices[0]: {response.choices[0]}")
                    if hasattr(response.choices[0], 'message'):
                        logger.info(f"ProxyAPI response.choices[0].message: {response.choices[0].message}")
                        if hasattr(response.choices[0].message, 'content'):
                            content_value = response.choices[0].message.content
                            logger.info(f"ProxyAPI response.choices[0].message.content type: {type(content_value)}")
                            logger.info(f"ProxyAPI response.choices[0].message.content: {repr(content_value)}")
            
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                # Пробуем разные способы получения контента
                content = None
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                elif hasattr(choice, 'text'):
                    content = choice.text
                elif hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                    content = choice.delta.content
                
                # Проверяем finish_reason
                finish_reason = getattr(choice, 'finish_reason', None)
                
                if content:
                    logger.info(f"ProxyAPI content length: {len(content)}")
                    if finish_reason == 'length':
                        logger.warning(f"ProxyAPI response was truncated (finish_reason='length'), content length: {len(content)}")
                    return content
                else:
                    # Если content пустой, проверяем finish_reason
                    if finish_reason == 'length':
                        logger.warning(f"ProxyAPI response was truncated before generating any content (finish_reason='length'). This may indicate max_completion_tokens is too low.")
                        # Пробуем повторить запрос с увеличенным лимитом, если текущий лимит меньше 8000
                        if Config.PROXYAPI_MAX_TOKENS < 8000:
                            logger.info(f"Retrying with increased max_completion_tokens: {Config.PROXYAPI_MAX_TOKENS * 2}")
                            try:
                                retry_response = await proxyapi_client.chat.completions.create(
                                    model=Config.PROXYAPI_MODEL,
                                    messages=api_messages,
                                    max_completion_tokens=min(Config.PROXYAPI_MAX_TOKENS * 2, 8000)
                                )
                                if retry_response.choices and len(retry_response.choices) > 0:
                                    retry_choice = retry_response.choices[0]
                                    retry_content = None
                                    if hasattr(retry_choice, 'message') and hasattr(retry_choice.message, 'content'):
                                        retry_content = retry_choice.message.content
                                    if retry_content:
                                        logger.info(f"ProxyAPI retry successful, content length: {len(retry_content)}")
                                        return retry_content
                            except Exception as retry_e:
                                logger.warning(f"ProxyAPI retry failed: {retry_e}")
                    else:
                        logger.warning(f"ProxyAPI content is empty or None. Finish reason: {finish_reason}, Choice structure: {choice}")
                    # Пробуем получить полный ответ как строку для отладки
                    try:
                        logger.warning(f"ProxyAPI full choice object: {repr(choice)}")
                    except:
                        pass
            else:
                logger.warning(f"ProxyAPI response has no choices or empty. Response: {response}")
                # Пробуем получить полный ответ как строку для отладки
                try:
                    logger.warning(f"ProxyAPI full response object: {repr(response)}")
                except:
                    pass
            
            logger.warning("Empty response from ProxyAPI, trying fallback")
            # If ProxyAPI returned empty response, try OpenRouter if available
            if openrouter_client:
                try_openrouter_fallback = True
            
        except asyncio.TimeoutError:
            logger.error("ProxyAPI timeout")
            raise APITimeoutError("ProxyAPI request timeout")
        except PermissionDeniedError as e:
            error_str = str(e)
            if "402" in error_str or "balance" in error_str.lower() or "insufficient" in error_str.lower():
                logger.warning(f"ProxyAPI недостаточно баланса (402), пробую OpenRouter как fallback: {e}")
                if openrouter_client:
                    try_openrouter_fallback = True
                else:
                    raise RateLimitError(f"ProxyAPI rate limit: {e}")
            else:
                logger.error(f"ProxyAPI PermissionDeniedError: {e}")
                raise InvalidInputError(f"ProxyAPI permission denied: {e}")
        except APIError as e:
            error_str = str(e)
            status_code = getattr(e, 'status_code', None)
            # Обработка ошибок 400 (неправильный параметр) и 402 (недостаточно баланса)
            if status_code == 429 or "rate limit" in error_str.lower():
                logger.warning(f"ProxyAPI rate limit, пробую OpenRouter как fallback: {e}")
                if openrouter_client:
                    try_openrouter_fallback = True
                else:
                    raise RateLimitError(f"ProxyAPI rate limit: {e}")
            elif status_code == 400:
                logger.warning(f"ProxyAPI ошибка параметра (400), пробую OpenRouter как fallback: {e}")
                if openrouter_client:
                    try_openrouter_fallback = True
                else:
                    raise InvalidInputError(f"ProxyAPI invalid input: {e}")
            elif status_code == 402 or "balance" in error_str.lower() or "insufficient" in error_str.lower():
                logger.warning(f"ProxyAPI недостаточно баланса (402), пробую OpenRouter как fallback: {e}")
                if openrouter_client:
                    try_openrouter_fallback = True
                else:
                    raise RateLimitError(f"ProxyAPI insufficient balance: {e}")
            else:
                logger.error(f"Error calling ProxyAPI: {e}", exc_info=True)
                raise APITimeoutError(f"ProxyAPI error: {e}")
        except Exception as e:
            error_str = str(e)
            # Обработка ошибок для обратной совместимости
            if "timeout" in error_str.lower():
                raise APITimeoutError(f"ProxyAPI timeout: {e}")
            elif "rate limit" in error_str.lower() or "429" in error_str:
                raise RateLimitError(f"ProxyAPI rate limit: {e}")
            elif "400" in error_str:
                if openrouter_client:
                    try_openrouter_fallback = True
                else:
                    raise InvalidInputError(f"ProxyAPI invalid input: {e}")
            elif "402" in error_str or "balance" in error_str.lower():
                if openrouter_client:
                    try_openrouter_fallback = True
                else:
                    raise RateLimitError(f"ProxyAPI insufficient balance: {e}")
            else:
                logger.error(f"Error calling ProxyAPI: {e}", exc_info=True)
                raise APITimeoutError(f"ProxyAPI unexpected error: {e}")
    
    # Try OpenRouter (if configured and selected, or as fallback from ProxyAPI)
    should_try_openrouter = False
    if Config.LLM_PROVIDER == "openrouter":
        should_try_openrouter = True
    elif try_openrouter_fallback:
        should_try_openrouter = True
    
    if openrouter_client and should_try_openrouter:
        if Config.LLM_PROVIDER == "proxyapi":
            logger.info(f"Использую OpenRouter как fallback (модель: {Config.OPENROUTER_MODEL})")
        else:
            logger.info(f"Использую OpenRouter (модель: {Config.OPENROUTER_MODEL})")
        try:
            response = await openrouter_client.chat.completions.create(
                model=Config.OPENROUTER_MODEL,
                messages=api_messages,
                temperature=0.3,
                max_tokens=Config.OPENROUTER_MAX_TOKENS
            )
            
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    return content
            
            logger.warning("Empty response from OpenRouter, returning fallback")
            
        except asyncio.TimeoutError:
            logger.error("OpenRouter timeout")
            raise APITimeoutError("OpenRouter request timeout")
        except PermissionDeniedError as e:
            error_str = str(e)
            if "403" in error_str or "region" in error_str.lower() or "not available" in error_str.lower():
                logger.warning(f"OpenRouter недоступен в вашем регионе (403): {e}")
                raise InvalidInputError(f"OpenRouter not available in region: {e}")
            else:
                logger.error(f"OpenRouter PermissionDeniedError: {e}")
                raise InvalidInputError(f"OpenRouter permission denied: {e}")
        except APIError as e:
            error_str = str(e)
            status_code = getattr(e, 'status_code', None)
            if status_code == 429 or "rate limit" in error_str.lower():
                raise RateLimitError(f"OpenRouter rate limit: {e}")
            elif status_code == 402 or "credits" in error_str.lower():
                raise RateLimitError(f"OpenRouter insufficient credits: {e}")
            elif status_code == 400:
                raise InvalidInputError(f"OpenRouter invalid input: {e}")
            else:
                logger.error(f"Error calling OpenRouter API: {e}", exc_info=True)
                raise APITimeoutError(f"OpenRouter error: {e}")
        except Exception as e:
            error_str = str(e)
            if "timeout" in error_str.lower():
                raise APITimeoutError(f"OpenRouter timeout: {e}")
            elif "rate limit" in error_str.lower() or "429" in error_str:
                raise RateLimitError(f"OpenRouter rate limit: {e}")
            elif "402" in error_str or "credits" in error_str.lower():
                raise RateLimitError(f"OpenRouter insufficient credits: {e}")
            else:
                logger.error(f"Error calling OpenRouter API: {e}", exc_info=True)
                raise APITimeoutError(f"OpenRouter unexpected error: {e}")
    
    return FALLBACK_MESSAGE

