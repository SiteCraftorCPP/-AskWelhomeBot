"""Управление контекстом сессии."""
from typing import Any, Optional
from aiogram.fsm.context import FSMContext


async def get_session_context(state: FSMContext) -> dict:
    """
    Получить полный контекст сессии из FSM state.
    
    Args:
        state: FSM контекст
        
    Returns:
        Словарь с контекстом сессии
    """
    data = await state.get_data()
    
    # Инициализация структуры контекста, если её нет
    if "collected_data" not in data:
        data["collected_data"] = {}
    if "asked_questions" not in data:
        data["asked_questions"] = []
    if "conversation_history" not in data:
        data["conversation_history"] = []
    
    # Инициализация collected_data, если её нет
    collected_data = data.get("collected_data", {})
    if "location" not in collected_data:
        collected_data["location"] = {}
    if "budget" not in collected_data:
        collected_data["budget"] = {}
    
    return {
        "selected_section": data.get("selected_section"),
        "collected_data": collected_data,
        "asked_questions": data.get("asked_questions", []),
        "conversation_history": data.get("conversation_history", []),
    }


async def update_session_context(
    state: FSMContext,
    field: str,
    value: Any,
    asked_question: Optional[str] = None
) -> None:
    """
    Обновить контекст сессии.
    
    Args:
        state: FSM контекст
        field: Поле для обновления (может быть вложенным через точку, например "location.city")
        value: Значение для установки
        asked_question: Ключ вопроса, который был задан (например "city", "property_type")
    """
    data = await state.get_data()
    
    # Инициализация структуры, если её нет
    if "collected_data" not in data:
        data["collected_data"] = {}
    if "asked_questions" not in data:
        data["asked_questions"] = []
    
    collected_data = data["collected_data"]
    
    # Обновление вложенных полей (например "location.city")
    if "." in field:
        parts = field.split(".")
        current = collected_data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    else:
        # Прямое обновление поля
        collected_data[field] = value
    
    # Отметка вопроса как заданного
    if asked_question and asked_question not in data["asked_questions"]:
        data["asked_questions"].append(asked_question)
    
    # Сохранение в state
    await state.update_data(
        collected_data=collected_data,
        asked_questions=data["asked_questions"]
    )


async def is_question_asked(state: FSMContext, question_key: str) -> bool:
    """
    Проверить, был ли задан вопрос.
    
    Args:
        state: FSM контекст
        question_key: Ключ вопроса (например "city", "property_type")
        
    Returns:
        True если вопрос был задан, False иначе
    """
    data = await state.get_data()
    asked_questions = data.get("asked_questions", [])
    return question_key in asked_questions


async def mark_question_asked(state: FSMContext, question_key: str) -> None:
    """
    Отметить вопрос как заданный.
    
    Args:
        state: FSM контекст
        question_key: Ключ вопроса (например "city", "property_type")
    """
    data = await state.get_data()
    
    if "asked_questions" not in data:
        data["asked_questions"] = []
    
    if question_key not in data["asked_questions"]:
        data["asked_questions"].append(question_key)
        await state.update_data(asked_questions=data["asked_questions"])


async def add_to_conversation_history(
    state: FSMContext,
    role: str,
    text: str
) -> None:
    """
    Добавить сообщение в историю разговора.
    
    Args:
        state: FSM контекст
        role: Роль ("U" для пользователя, "B" для бота)
        text: Текст сообщения
    """
    data = await state.get_data()
    
    if "conversation_history" not in data:
        data["conversation_history"] = []
    
    # Ограничение истории (последние 50 сообщений)
    history = data["conversation_history"]
    history.append({"role": role, "text": text})
    
    # Ограничиваем до последних 50 сообщений
    if len(history) > 50:
        history = history[-50:]
    
    await state.update_data(conversation_history=history)
