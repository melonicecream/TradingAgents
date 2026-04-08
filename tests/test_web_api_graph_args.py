import unittest

from web_api.main import build_web_graph_runtime_args


class WebApiGraphArgsTests(unittest.TestCase):
    def test_build_web_graph_runtime_args_uses_sync_durability_and_thread_id(self):
        self.assertEqual(
            build_web_graph_runtime_args("thread-123"),
            {
                "durability": "sync",
                "config": {"configurable": {"thread_id": "thread-123"}},
            },
        )


if __name__ == "__main__":
    unittest.main()
