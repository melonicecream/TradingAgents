import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI

from web_api.db.database import bootstrap_checkpointer, _sqlite_conn_string
from web_api.main import lifespan


class WebApiBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_conn_string_uses_existing_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "tradingagents.db"
            database_url = f"sqlite+aiosqlite:///{db_path}"

            self.assertEqual(_sqlite_conn_string(database_url), str(db_path))

    async def test_bootstrap_checkpointer_uses_temp_sqlite_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "tradingagents.db"
            database_url = f"sqlite+aiosqlite:///{db_path}"
            fake_checkpointer = SimpleNamespace(setup=AsyncMock())

            @asynccontextmanager
            async def fake_from_conn_string(conn_string: str):
                self.assertEqual(conn_string, str(db_path))
                yield fake_checkpointer

            with patch(
                "web_api.db.database.AsyncSqliteSaver.from_conn_string",
                new=fake_from_conn_string,
            ):
                async with bootstrap_checkpointer(database_url) as checkpointer:
                    self.assertIs(checkpointer, fake_checkpointer)
                    self.assertTrue(db_path.parent.exists())

            fake_checkpointer.setup.assert_awaited_once()

    async def test_lifespan_bootstraps_checkpointer_for_web_api_only(self):
        app = FastAPI()
        db_initializer = AsyncMock()
        fake_checkpointer = object()

        @asynccontextmanager
        async def fake_bootstrap(database_url: str | None = None):
            self.assertEqual(
                database_url, "sqlite+aiosqlite:///./data/tradingagents.db"
            )
            yield fake_checkpointer

        async with lifespan(
            app,
            checkpointer_bootstrap=fake_bootstrap,
            db_initializer=db_initializer,
        ):
            self.assertIs(app.state.checkpointer, fake_checkpointer)

        db_initializer.assert_awaited_once()
        self.assertIsNone(app.state.checkpointer)


if __name__ == "__main__":
    unittest.main()
