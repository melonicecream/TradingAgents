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

    async def reply_text(self, text, reply_markup=None):
        self.replies.append({"text": text, "reply_markup": reply_markup})
        return SimpleNamespace(edit_text=AsyncMock())


class FakeQuery:
    def __init__(self, data: str, message: FakeMessage | None = None):
        self.data = data
        self.message = message or FakeMessage()
        self.answered = False
        self.edits = []

    async def answer(self):
        self.answered = True

    async def edit_message_text(self, text, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def edit_message_reply_markup(self, reply_markup=None):
        self.edits.append({"reply_markup": reply_markup})


class TelegramHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_command_sends_main_menu(self):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=1), effective_message=message
        )
        context = SimpleNamespace(
            user_data={}, bot_data={"settings": SimpleNamespace(allowed_chat_id=1)}
        )

        await telegram_main.start_command(update, context)

        self.assertEqual(len(message.replies), 1)
        self.assertIn(
            "개인용 TradingAgents Telegram 인터페이스", message.replies[0]["text"]
        )

    async def test_invalid_date_keeps_date_mode(self):
        message = FakeMessage(text="2026/01/01")
        context = SimpleNamespace(
            user_data={
                "telegram_mode": "await_date",
                "draft_analysis": telegram_main.DraftAnalysis(ticker="AAPL"),
            },
            bot_data={"settings": SimpleNamespace(allowed_chat_id=1)},
            application=FakeApplication(),
        )
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=1), effective_message=message
        )

        await telegram_main.handle_text(update, context)

        self.assertEqual(context.user_data["telegram_mode"], "await_date")
        self.assertIn("YYYY-MM-DD", message.replies[-1]["text"])

    async def test_date_callback_starts_background_analysis(self):
        query = FakeQuery("date:2026-04-20")
        context = SimpleNamespace(
            user_data={
                "telegram_mode": "await_date",
                "draft_analysis": telegram_main.DraftAnalysis(
                    ticker="AAPL", analysis_date="2026-04-19"
                ),
            },
            bot_data={"settings": SimpleNamespace(allowed_chat_id=1)},
            application=FakeApplication(),
        )
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=1), callback_query=query
        )

        with patch("telegram_bot.main._run_analysis", AsyncMock()):
            await telegram_main.handle_menu(update, context)

        self.assertIsNone(context.user_data["telegram_mode"])
        self.assertEqual(
            context.user_data["draft_analysis"].analysis_date, "2026-04-20"
        )
        self.assertEqual(len(context.application.created_tasks), 1)

    async def test_run_analysis_completion_sends_summary_before_detail(self):
        message = FakeMessage()
        draft = telegram_main.DraftAnalysis(
            ticker="AAPL", analysis_date="2026-04-18", analysts={"market"}
        )

        class FakeService:
            async def stream_analysis(self, *args, **kwargs):
                yield {
                    "type": "progress",
                    "progress": 50,
                    "current_stage": "시장 분석",
                    "completed_milestones": 1,
                    "total_milestones": 5,
                    "elapsed_seconds": 12,
                }
                yield {"type": "complete", "decision": "Buy", "execution_id": 1}

            async def get_execution_detail(self, execution_id):
                return {
                    "id": 1,
                    "ticker": "AAPL",
                    "status": "완료",
                    "progress": 100,
                    "analysis_date": "2026-04-18",
                    "current_stage": "포트폴리오 결정",
                    "decision": "Buy",
                    "summary_report": "최종 한글 요약",
                    "reports": {},
                    "research": {},
                    "risk": {},
                    "started_at": "2026-04-18T10:00:00",
                    "updated_at": "2026-04-18T10:05:00",
                    "elapsed_seconds": 300,
                    "workflow_steps": [],
                    "analysts": ["market"],
                }

        with patch("telegram_bot.main.SERVICE", FakeService()):
            await telegram_main._run_analysis(message, draft)

        self.assertGreaterEqual(len(message.replies), 3)
        self.assertIn("최종 요약", message.replies[1]["text"])
        self.assertIn("실행 상세", message.replies[2]["text"])

    def test_is_valid_date(self):
        is_valid_date = getattr(telegram_main, "_is_valid_date")
        self.assertTrue(is_valid_date("2026-04-18"))
        self.assertFalse(is_valid_date("2026/04/18"))


if __name__ == "__main__":
    unittest.main()
