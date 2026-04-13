"""Telegram bot entrypoint for personal TradingAgents usage."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Optional, cast

from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_bot.config import TelegramBotSettings, load_settings
from telegram_bot.presenter import (
    build_analyst_menu,
    build_date_menu,
    build_execution_detail_menu,
    build_execution_menu,
    build_main_menu,
    format_engine_info,
    format_execution_detail,
    format_help_text,
    format_progress_message,
    format_section_messages,
    format_startup_guide,
    format_system_stats,
)
from telegram_bot.service import TelegramAnalysisService, default_analysis_date
from cli.utils import normalize_ticker_symbol
import datetime as dt


logger = logging.getLogger(__name__)


@dataclass
class DraftAnalysis:
    ticker: Optional[str] = None
    analysis_date: str = field(default_factory=default_analysis_date)
    analysts: set[str] = field(
        default_factory=lambda: {"market", "social", "news", "fundamentals"}
    )


SERVICE = TelegramAnalysisService()
SESSION_KEY = "draft_analysis"
MODE_KEY = "telegram_mode"
TASK_KEY = "analysis_task"


def _get_draft(context: ContextTypes.DEFAULT_TYPE) -> DraftAnalysis:
    user_data = cast(dict[str, Any], context.user_data)
    draft = user_data.get(SESSION_KEY)
    if draft is None:
        draft = DraftAnalysis()
        user_data[SESSION_KEY] = draft
    return draft


def _chat_allowed(update: Update, settings: TelegramBotSettings) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id == settings.allowed_chat_id


async def _reject_if_needed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    bot_data = cast(dict[str, Any], context.bot_data)
    settings: TelegramBotSettings = bot_data["settings"]
    if _chat_allowed(update, settings):
        return False
    effective_message = update.effective_message
    if effective_message:
        await cast(Any, effective_message).reply_text(
            "이 봇은 현재 허용된 개인 채팅에서만 사용할 수 있습니다."
        )
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_if_needed(update, context):
        return
    user_data = cast(dict[str, Any], context.user_data)
    user_data.clear()
    message = cast(Any, update.effective_message)
    await message.reply_text(
        "개인용 TradingAgents Telegram 인터페이스입니다.",
        reply_markup=build_main_menu(),
    )


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_if_needed(update, context):
        return

    query = update.callback_query
    assert query is not None
    user_data = cast(dict[str, Any], context.user_data)
    application = cast(Any, context.application)
    await query.answer()
    data = query.data or ""

    if data == "menu:root":
        user_data.clear()
        await _safe_edit_text(query, "메인 메뉴입니다.", reply_markup=build_main_menu())
        return

    if data == "menu:new_analysis":
        draft = DraftAnalysis()
        user_data[SESSION_KEY] = draft
        user_data[MODE_KEY] = "await_ticker"
        query_message = cast(Any, query.message)
        reply_markup = None
        existing_markup = getattr(query_message, "reply_markup", None)
        if existing_markup:
            reply_markup = InlineKeyboardMarkup(
                [[existing_markup.inline_keyboard[0][0]]]
            )
        await _safe_edit_text(
            query,
            "분석할 종목 코드를 보내주세요.\n예: AAPL, TSLA, 005930.KS",
            reply_markup=reply_markup,
        )
        return

    if data == "menu:engine":
        engine = await SERVICE.get_engine_info()
        await _safe_edit_text(
            query, format_engine_info(engine), reply_markup=build_main_menu()
        )
        return

    if data == "menu:stats":
        stats = await SERVICE.get_stats()
        await _safe_edit_text(
            query, format_system_stats(stats), reply_markup=build_main_menu()
        )
        return

    if data == "menu:help":
        await _safe_edit_text(query, format_help_text(), reply_markup=build_main_menu())
        return

    if data == "menu:executions":
        items = await SERVICE.get_recent_executions()
        text = "최근 실행 목록입니다.\n버튼을 눌러 상세를 열 수 있습니다."
        await _safe_edit_text(query, text, reply_markup=build_execution_menu(items))
        return

    if data.startswith("analyst:"):
        draft = _get_draft(context)
        action = data.split(":", 1)[1]
        if action == "done":
            user_data[MODE_KEY] = "await_date"
            await _safe_edit_text(
                query,
                f"분석 날짜를 보내주세요.\n형식: YYYY-MM-DD\n기본값: {draft.analysis_date}",
                reply_markup=build_date_menu(draft.analysis_date),
            )
            return

        if action in draft.analysts:
            draft.analysts.remove(action)
        else:
            draft.analysts.add(action)
        await query.edit_message_reply_markup(
            reply_markup=build_analyst_menu(draft.analysts)
        )
        return

    if data.startswith("date:"):
        draft = _get_draft(context)
        draft.analysis_date = data.split(":", 1)[1]
        user_data[MODE_KEY] = None
        await _safe_edit_text(
            query,
            f"분석을 시작합니다.\n- 종목: {draft.ticker}\n- 날짜: {draft.analysis_date}\n- 분석가: {', '.join(sorted(draft.analysts))}",
            reply_markup=build_main_menu(),
        )
        application.create_task(_run_analysis(cast(Any, query.message), draft))
        return

    if data.startswith("execution:"):
        execution_id = int(data.split(":", 1)[1])
        detail = await SERVICE.get_execution_detail(execution_id)
        await _safe_edit_text(
            query,
            format_execution_detail(detail),
            reply_markup=build_execution_detail_menu(execution_id),
        )
        return

    if data.startswith("execution_section:"):
        _prefix, execution_id_raw, section = data.split(":", 2)
        detail = await SERVICE.get_execution_detail(int(execution_id_raw))
        chunks = format_section_messages(detail, section)
        query_message = cast(Any, query.message)
        for chunk in chunks:
            await query_message.reply_text(chunk)
        await query.edit_message_reply_markup(
            reply_markup=build_execution_detail_menu(int(execution_id_raw))
        )
        return


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_if_needed(update, context):
        return

    user_data = cast(dict[str, Any], context.user_data)
    application = cast(Any, context.application)
    message = cast(Any, update.effective_message)
    assert message is not None
    mode = user_data.get(MODE_KEY)
    draft = _get_draft(context)
    text = (message.text or "").strip()

    if mode == "await_ticker":
        if not text:
            await message.reply_text(
                "종목 코드를 입력해주세요. 예: AAPL, TSLA, 005930.KS"
            )
            return
        draft.ticker = normalize_ticker_symbol(text)
        user_data[MODE_KEY] = "await_analysts"
        await message.reply_text(
            f"종목: {draft.ticker}\n분석가를 선택하세요.",
            reply_markup=build_analyst_menu(draft.analysts),
        )
        return

    if mode == "await_date":
        if not _is_valid_date(text):
            await message.reply_text(
                f"날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 보내주세요.\n기본값을 쓰려면 버튼을 눌러주세요: {draft.analysis_date}",
                reply_markup=build_date_menu(draft.analysis_date),
            )
            return
        draft.analysis_date = text or draft.analysis_date
        user_data[MODE_KEY] = None
        await message.reply_text(
            f"분석을 시작합니다.\n- 종목: {draft.ticker}\n- 날짜: {draft.analysis_date}\n- 분석가: {', '.join(sorted(draft.analysts))}",
            reply_markup=build_main_menu(),
        )
        task = application.create_task(_run_analysis(message, draft))
        user_data[TASK_KEY] = task
        return

    await message.reply_text(
        "메뉴에서 작업을 선택해주세요.", reply_markup=build_main_menu()
    )


async def _run_analysis(message, draft: DraftAnalysis) -> None:
    if not draft.ticker:
        await message.reply_text("종목 코드가 없습니다. 새 분석을 다시 시작해주세요.")
        return

    status_message = await message.reply_text("분석 준비 중...")
    final_payload: Optional[dict[str, Any]] = None

    async for event in SERVICE.stream_analysis(
        ticker=draft.ticker,
        analysis_date=draft.analysis_date,
        analysts=sorted(draft.analysts),
    ):
        event_type = event.get("type")
        if event_type == "progress":
            await _safe_edit_text(
                status_message,
                format_progress_message(event, draft.ticker, draft.analysis_date),
            )
        elif event_type == "complete":
            final_payload = event
            break
        elif event_type == "error":
            await _safe_edit_text(
                status_message,
                f"분석 중 오류가 발생했습니다.\n- 상태: {event.get('status')}\n- 마지막 단계: {event.get('last_completed_milestone') or '-'}\n- 오류: {event.get('error')}",
            )
            return

    if not final_payload:
        await _safe_edit_text(status_message, "분석이 중단되었습니다.")
        return

    await _safe_edit_text(
        status_message,
        f"✅ 분석 완료\n- 종목: {draft.ticker}\n- 최종 판단: {final_payload.get('decision')}\n- 실행 ID: {final_payload.get('execution_id')}",
    )

    detail = await SERVICE.get_execution_detail(int(final_payload["execution_id"]))
    for chunk in format_section_messages(detail, "summary"):
        await message.reply_text(chunk)
    await message.reply_text(
        format_execution_detail(detail),
        reply_markup=build_execution_detail_menu(int(final_payload["execution_id"])),
    )


async def _post_init(_application: Application) -> None:
    await SERVICE.ensure_ready()
    settings = cast(TelegramBotSettings, _application.bot_data["settings"])
    try:
        await _application.bot.send_message(
            chat_id=settings.allowed_chat_id,
            text=format_startup_guide(),
            reply_markup=build_main_menu(),
        )
    except TimedOut:
        logger.warning("Telegram startup guide send timed out.")
    except NetworkError as exc:
        logger.warning("Telegram startup guide send failed: %s", exc)


async def _safe_edit_text(message: Any, text: str, reply_markup: Any = None) -> None:
    try:
        edit_fn = getattr(message, "edit_text", None) or getattr(
            message, "edit_message_text", None
        )
        if edit_fn is None:
            return
        await edit_fn(text, reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return
        raise
    except TimedOut:
        logger.warning("Telegram message edit timed out.")
    except NetworkError as exc:
        logger.warning("Telegram message edit failed: %s", exc)


def build_application(settings: TelegramBotSettings) -> Application:
    application = (
        Application.builder()
        .token(settings.token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .connection_pool_size(20)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(90.0)
        .get_updates_write_timeout(30.0)
        .get_updates_pool_timeout(30.0)
        .get_updates_connection_pool_size(20)
        .post_init(_post_init)
        .build()
    )
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_menu))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    return application


def _is_valid_date(value: str) -> bool:
    try:
        dt.datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main() -> None:
    settings = load_settings()
    app = build_application(settings)
    app.run_polling(bootstrap_retries=5)


if __name__ == "__main__":
    main()
