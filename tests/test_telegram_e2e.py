import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import telegram_bot.main as telegram_main


class FakeApplication:
    def __init__(self):
        self.created_tasks = []

    def create_task(self, coro):
        self.created_tasks.append(coro)
        if inspect.iscoroutine(coro):
            coro.close()
        return coro


class FakeMessage:
    def __init__(self, text: str | None = None):
        self.text = text
        self.replies = []
        self.reply_markup = None

    async def reply_text(self, text, reply_markup=None):
        self.replies.append({"text": text, "reply_markup": reply_markup})
        self.reply_markup = reply_markup
        return SimpleNamespace(edit_text=AsyncMock())


class FakeQuery:
    def __init__(self, data: str, message: FakeMessage | None = None):
        self.data = data
        self.message = message or FakeMessage()
        self.edits = []

    async def answer(self):
        return None

    async def edit_message_text(self, text, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def edit_message_reply_markup(self, reply_markup=None):
        self.edits.append({"reply_markup": reply_markup})


class TelegramE2ETests(unittest.IsolatedAsyncioTestCase):
    async def test_menu_driven_new_analysis_flow_reaches_background_start(self):
        app = FakeApplication()
        context = SimpleNamespace(
            user_data={},
            bot_data={"settings": SimpleNamespace(allowed_chat_id=1)},
            application=app,
        )

        start_message = FakeMessage()
        start_update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=1),
            effective_message=start_message,
        )
        await telegram_main.start_command(start_update, context)

        query_new = FakeQuery("menu:new_analysis", FakeMessage())
        await telegram_main.handle_menu(
            SimpleNamespace(
                effective_chat=SimpleNamespace(id=1), callback_query=query_new
            ),
            context,
        )

        ticker_message = FakeMessage("MSFT")
        await telegram_main.handle_text(
            SimpleNamespace(
                effective_chat=SimpleNamespace(id=1), effective_message=ticker_message
            ),
            context,
        )

        query_done = FakeQuery("analyst:done", FakeMessage())
        await telegram_main.handle_menu(
            SimpleNamespace(
                effective_chat=SimpleNamespace(id=1), callback_query=query_done
            ),
            context,
        )

        with patch("telegram_bot.main._run_analysis", AsyncMock()):
            query_date = FakeQuery("date:2026-04-18", FakeMessage())
            await telegram_main.handle_menu(
                SimpleNamespace(
                    effective_chat=SimpleNamespace(id=1), callback_query=query_date
                ),
                context,
            )

        self.assertEqual(context.user_data["draft_analysis"].ticker, "MSFT")
        self.assertEqual(
            context.user_data["draft_analysis"].analysis_date, "2026-04-18"
        )
        self.assertEqual(len(app.created_tasks), 1)

    async def test_execution_section_sends_multiple_chunks_for_long_report(self):
        long_text = ("긴 리포트 문단\n\n" * 600).strip()

        class FakeService:
            async def get_execution_detail(self, execution_id):
                return {
                    "id": execution_id,
                    "ticker": "AAPL",
                    "status": "완료",
                    "progress": 100,
                    "analysis_date": "2026-04-18",
                    "current_stage": "포트폴리오 결정",
                    "decision": "Buy",
                    "summary_report": "요약",
                    "reports": {"market": long_text},
                    "research": {},
                    "risk": {},
                    "started_at": "2026-04-18T10:00:00",
                    "updated_at": "2026-04-18T10:05:00",
                    "elapsed_seconds": 300,
                    "workflow_steps": [],
                    "analysts": ["market"],
                }

        query_message = FakeMessage()
        query = FakeQuery("execution_section:99:reports", query_message)
        context = SimpleNamespace(
            user_data={},
            bot_data={"settings": SimpleNamespace(allowed_chat_id=1)},
            application=FakeApplication(),
        )

        with patch("telegram_bot.main.SERVICE", FakeService()):
            await telegram_main.handle_menu(
                SimpleNamespace(
                    effective_chat=SimpleNamespace(id=1), callback_query=query
                ),
                context,
            )

        self.assertGreater(len(query_message.replies), 1)
        self.assertTrue(
            all(len(reply["text"]) <= 3900 for reply in query_message.replies)
        )


if __name__ == "__main__":
    unittest.main()
