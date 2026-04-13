import unittest

from telegram_bot.presenter import (
    build_analyst_menu,
    build_execution_detail_menu,
    build_execution_menu,
    build_main_menu,
    format_duration,
    split_long_message,
)


class TelegramPresenterTests(unittest.TestCase):
    def test_split_long_message_breaks_large_text(self):
        text = ("요약 문단\n\n" * 700).strip()

        chunks = split_long_message(text, limit=500)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))

    def test_main_menu_contains_core_entries(self):
        markup = build_main_menu()
        labels = [button.text for row in markup.inline_keyboard for button in row]

        self.assertIn("새 분석", labels)
        self.assertIn("실행 목록", labels)
        self.assertIn("시스템 현황", labels)
        self.assertIn("엔진 정보", labels)

    def test_analyst_menu_marks_selected_items(self):
        markup = build_analyst_menu({"market", "news"})
        labels = [row[0].text for row in markup.inline_keyboard[:-1]]

        self.assertTrue(any(label.startswith("✅ 시장") for label in labels))
        self.assertTrue(any(label.startswith("✅ 뉴스") for label in labels))
        self.assertTrue(any(label.startswith("⬜ 소셜") for label in labels))

    def test_execution_menu_and_detail_menu_use_short_callbacks(self):
        menu = build_execution_menu(
            [{"id": 12, "ticker": "AAPL", "status": "분석 중", "progress": 55.0}]
        )
        detail = build_execution_detail_menu(12)

        execution_callback = menu.inline_keyboard[0][0].callback_data
        detail_callbacks = [
            button.callback_data for row in detail.inline_keyboard for button in row
        ]

        self.assertLessEqual(len(execution_callback), 64)
        self.assertTrue(all(len(callback) <= 64 for callback in detail_callbacks))

    def test_format_duration_handles_seconds_and_minutes(self):
        self.assertEqual(format_duration(9), "9초")
        self.assertEqual(format_duration(75), "1분 15초")
        self.assertEqual(format_duration(3675), "1시간 1분 15초")


if __name__ == "__main__":
    unittest.main()
