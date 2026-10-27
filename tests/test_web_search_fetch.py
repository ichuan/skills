from __future__ import annotations

import http.server
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "skills" / "web-search-fetch" / "scripts" / "web.py"


class _UnicodeHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = """<!doctype html>
<html><head><title>测试页面 🚀</title></head>
<body><main><h1>你好，世界 🌍</h1><p>特殊字符：€ café</p></main></body></html>
""".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


class WebSearchFetchTests(unittest.TestCase):
    def test_fetch_writes_unicode_from_any_working_directory(self) -> None:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _UnicodeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as working_directory:
                environment = os.environ.copy()
                environment["PYTHONIOENCODING"] = "gbk"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT_PATH),
                        "fetch",
                        f"http://127.0.0.1:{server.server_port}/article",
                        "--full",
                    ],
                    cwd=working_directory,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("你好，世界 🌍", result.stdout)
        self.assertIn("测试页面 🚀", result.stderr)


if __name__ == "__main__":
    unittest.main()
