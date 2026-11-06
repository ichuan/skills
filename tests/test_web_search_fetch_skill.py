from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "skills" / "web-search-fetch" / "scripts" / "web.py"


def load_web_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"missing web script: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("web_search_fetch_web", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "text/html; charset=utf-8", url: str = "https://example.com/page"):
        self._body = body
        self.headers = {"Content-Type": content_type}
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self._body[:limit] if limit and limit > 0 else self._body

    def geturl(self) -> str:
        return self._url


class HtmlToMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.web = load_web_module()

    def convert(self, html: str) -> tuple[str, str]:
        return self.web.html_to_markdown(html)

    def test_headings_paragraphs_and_inline_formatting(self):
        title, md = self.convert(
            "<html><head><title>My Page</title></head><body>"
            "<h1>Title</h1><p>Hello <b>bold</b> and <i>italic</i> text.</p>"
            "<p>See <a href='https://example.com/docs'>the docs</a>.</p>"
            "</body></html>"
        )
        self.assertEqual(title, "My Page")
        self.assertIn("# Title", md)
        self.assertIn("Hello **bold** and *italic* text.", md)
        self.assertIn("[the docs](https://example.com/docs)", md)

    def test_title_text_does_not_leak_into_body(self):
        title, md = self.convert(
            "<html><head><title>My Page</title></head><body><p>body text</p></body></html>"
        )
        self.assertEqual(title, "My Page")
        self.assertNotIn("My Page", md)
        self.assertIn("body text", md)

    def test_inline_spacing_is_preserved(self):
        _, md = self.convert("<p>a <b>b</b> c</p>")
        self.assertIn("a **b** c", md)

    def test_inline_code_keeps_leading_space(self):
        _, md = self.convert("<p>Use <code>print()</code> here.</p>")
        self.assertIn("Use `print()` here.", md)

    def test_backslash_is_escaped_exactly_once(self):
        _, md = self.convert("<p>a\\b path C:\\dir</p>")
        self.assertIn("a\\\\b", md)
        self.assertIn("C:\\\\dir", md)

    def test_unordered_and_ordered_lists(self):
        _, md = self.convert(
            "<ul><li>one</li><li>two</li></ul><ol><li>first</li><li>second</li></ol>"
        )
        self.assertIn("- one", md)
        self.assertIn("- two", md)
        self.assertIn("1. first", md)
        self.assertIn("2. second", md)

    def test_nested_list_keeps_parent_item_text(self):
        _, md = self.convert(
            "<ul><li>parent<ul><li>child</li></ul></li></ul>"
        )
        self.assertIn("- parent", md)
        self.assertIn("  - child", md)

    def test_code_blocks_and_inline_code(self):
        _, md = self.convert(
            "<p>Use <code>print()</code> here.</p>"
            "<pre><code class='language-python'>def f():\n    return 1</code></pre>"
        )
        self.assertIn("Use `print()` here.", md)
        self.assertIn("```python", md)
        self.assertIn("def f():", md)
        self.assertIn("return 1", md)

    def test_blockquote(self):
        _, md = self.convert("<blockquote><p>quoted words</p></blockquote>")
        self.assertIn("> quoted words", md)

    def test_blockquote_keeps_paragraph_separation(self):
        _, md = self.convert("<blockquote><p>aaa</p><p>bbb</p></blockquote>")
        self.assertIn("> aaa", md)
        self.assertIn("> bbb", md)
        self.assertNotIn("aaabbb", md)

    def test_table_with_header_row(self):
        _, md = self.convert(
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>a</td><td>1</td></tr></table>"
        )
        self.assertIn("| Name | Value |", md)
        self.assertIn("| --- | --- |", md)
        self.assertIn("| a | 1 |", md)

    def test_noisy_subtrees_are_stripped(self):
        _, md = self.convert(
            "<nav>menu home about</nav>"
            "<script>var x = 1;</script>"
            "<style>body { color: red; }</style>"
            "<p>real content</p>"
            "<footer>copyright junk</footer>"
        )
        self.assertNotIn("menu", md)
        self.assertNotIn("var x", md)
        self.assertNotIn("color: red", md)
        self.assertNotIn("copyright", md)
        self.assertIn("real content", md)

    def test_images_keep_alt_and_src(self):
        _, md = self.convert("<p><img src='/a.png' alt='pic'>after</p>")
        self.assertIn("![pic](/a.png)", md)

    def test_relative_urls_resolved_against_base_url(self):
        _, md = self.web.html_to_markdown(
            "<p><a href='/docs/x'>link</a> <img src='img/y.png'></p>",
            base_url="https://example.com/page/",
        )
        self.assertIn("[link](https://example.com/docs/x)", md)
        self.assertIn("(https://example.com/page/img/y.png)", md)

    def test_cjk_text_survives_conversion(self):
        _, md = self.convert("<p>中文内容测试。</p>")
        self.assertIn("中文内容测试", md)

    def test_code_fence_grows_around_embedded_backticks(self):
        _, md = self.convert("<pre>a ``` b</pre>")
        self.assertIn("````\na ``` b\n````", md)

    def test_unsafe_and_empty_links_drop_to_plain_text(self):
        _, md = self.convert(
            "<p><a href='#'>skip</a> <a href='javascript:x()'>js</a> <a href='https://ok.com'>ok</a></p>"
        )
        self.assertIn("skip", md)
        self.assertIn("js", md)
        self.assertNotIn("javascript:", md)
        self.assertIn("[ok](https://ok.com)", md)

    def test_lazy_images_use_data_src(self):
        _, md = self.convert("<img src='data:placeholder' data-src='/real.png' alt='lazy'>")
        self.assertIn("![lazy](/real.png)", md)

    def test_rowspan_cell_spans_rows(self):
        _, md = self.convert(
            "<table><tr><td rowspan='2'>x</td><td>1</td></tr><tr><td>2</td></tr></table>"
        )
        self.assertIn("| x | 1 |", md)
        self.assertIn("| 2 |", md)

    def test_implicitly_closed_paragraphs_and_list_items(self):
        _, md = self.convert("<p>one<p>two<ul><li>a<li>b</ul>")
        self.assertIn("one", md)
        self.assertIn("two", md)
        self.assertIn("- a", md)
        self.assertIn("- b", md)

    def test_main_content_drops_page_chrome(self):
        html = (
            "<html><head><title>Site</title></head><body>"
            "<nav><a href='/home'>Home</a> <a href='/about'>About</a></nav>"
            "<article><h1>Story</h1>"
            "<p>Body paragraph with enough real substance that it dominates the page and "
            "is kept as the main content of the document.</p>"
            "<div class='share'><a href='https://www.facebook.com/sharer.php?u=x'>Share</a></div>"
            "<div class='related'><a href='/r1'>Related one</a> <a href='/r2'>Related two</a> "
            "<a href='/r3'>Related three</a></div>"
            "</article>"
            "<footer><a href='/tos'>Terms</a></footer>"
            "</body></html>"
        )
        _, md = self.web.html_to_markdown(html, main_content=True)
        self.assertIn("# Story", md)
        self.assertIn("Body paragraph with enough real substance", md)
        self.assertNotIn("sharer.php", md)
        self.assertNotIn("Related one", md)
        self.assertNotIn("Home", md)
        self.assertNotIn("Terms", md)

    def test_main_content_title_fallback_without_h1(self):
        html = (
            "<html><head><title>Fallback Title</title></head><body>"
            "<article><p>An article with no heading element at all, but carrying enough "
            "text mass that the scope selection still finds it reliably.</p></article>"
            "</body></html>"
        )
        _, md = self.web.html_to_markdown(html, main_content=True)
        self.assertIn("# Fallback Title", md)
        self.assertIn("no heading element at all", md)

    def test_main_content_keeps_link_list_pages(self):
        html = (
            "<html><body><div>"
            "<a href='/1'>First resource with a name</a> <a href='/2'>Second resource name</a> "
            "<a href='/3'>Third resource name</a> <a href='/4'>Fourth resource name</a>"
            "</div></body></html>"
        )
        _, md = self.web.html_to_markdown(html, main_content=True)
        self.assertIn("First resource with a name", md)
        self.assertIn("Fourth resource name", md)


class BraveSearchTests(unittest.TestCase):
    def setUp(self):
        self.web = load_web_module()
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_missing_api_key_exits_with_error(self):
        os.environ.pop("WEBSEARCH_API_KEY", None)
        os.environ.pop("BRAVE_API_KEY", None)
        with self.assertRaises(SystemExit):
            self.web.brave_search("query", 5)

    def test_results_are_parsed_to_url_title_snippet(self):
        payload = {
            "web": {
                "results": [
                    {"url": "https://a.example", "title": "A", "description": "about a"},
                    {"url": "https://b.example", "title": "B", "description": "about b"},
                ]
            }
        }
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["token"] = req.get_header("X-subscription-token")
            return FakeResponse(json.dumps(payload).encode(), content_type="application/json")

        original_urlopen = self.web.urllib.request.urlopen
        self.web.urllib.request.urlopen = fake_urlopen
        try:
            os.environ["WEBSEARCH_API_KEY"] = "test-key"
            results = self.web.run_search("anything", 5)
        finally:
            self.web.urllib.request.urlopen = original_urlopen

        self.assertEqual(captured["token"], "test-key")
        self.assertIn("q=anything", captured["url"])
        self.assertEqual(
            results,
            [
                {"url": "https://a.example", "title": "A", "snippet": "about a"},
                {"url": "https://b.example", "title": "B", "snippet": "about b"},
            ],
        )

    def test_missing_provider_configuration_exits_with_error(self):
        with self.assertRaises(SystemExit):
            self.web.run_search("query", 5)

    def test_brave_key_takes_priority_over_alias_and_rustxng(self):
        os.environ.update(BRAVE_API_KEY="brave-key", WEBSEARCH_API_KEY="legacy-key",
                          RUSTXNG_URL="https://unused.example")
        def respond(req, timeout=None):
            self.assertEqual(req.get_header("X-subscription-token"), "brave-key")
            return FakeResponse(b'{"web":{"results":[]}}')
        with patch.object(self.web.urllib.request, "urlopen", side_effect=respond):
            self.assertEqual(self.web.run_search("query", 5), [])


class RustXNGSearchTests(unittest.TestCase):
    def setUp(self):
        self.web = load_web_module()
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.requests = []
        self.status = 200
        self.brave_status = 429
        self.payload = {"results": [{"url": "https://example.com", "title": "Example", "content": "Snippet"}]}
        case = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                case.requests.append((self.path, self.headers.get("Authorization")))
                if self.path.startswith("/brave?"):
                    self.send_response(case.brave_status)
                    self.end_headers()
                    self.wfile.write(b'{"error":"quota exceeded"}')
                    return
                self.send_response(case.status)
                if case.status == 302:
                    self.send_header("Location", "/redirect-target")
                self.end_headers()
                self.wfile.write(json.dumps(case.payload).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        os.environ["RUSTXNG_URL"] = f"http://127.0.0.1:{server.server_port}/instance/"

    def test_brave_quota_errors_fall_back_once(self):
        os.environ.update(BRAVE_API_KEY="brave-key", RUSTXNG_TOKEN="rust-token")
        self.web.BRAVE_ENDPOINT = os.environ["RUSTXNG_URL"].removesuffix("instance/") + "brave"
        for status in (402, 429):
            with self.subTest(status=status):
                self.requests.clear()
                self.brave_status = status
                result = self.web.run_search("quota test", 3)
                self.assertEqual(result, [{"url": "https://example.com", "title": "Example", "snippet": "Snippet"}])
                self.assertEqual(len(self.requests), 2)
                self.assertTrue(self.requests[0][0].startswith("/brave?"))
                self.assertEqual(self.requests[1][1], "Bearer rust-token")

    def test_other_brave_errors_do_not_fall_back(self):
        os.environ["BRAVE_API_KEY"] = "brave-key"
        self.web.BRAVE_ENDPOINT = os.environ["RUSTXNG_URL"].removesuffix("instance/") + "brave"
        for status in (401, 403, 500):
            with self.subTest(status=status):
                self.requests.clear()
                self.brave_status = status
                with self.assertRaises(SystemExit):
                    self.web.run_search("query", 3)
                self.assertEqual(len(self.requests), 1)

    def test_quota_error_without_rustxng_reports_failure(self):
        os.environ["BRAVE_API_KEY"] = "brave-key"
        self.web.BRAVE_ENDPOINT = os.environ.pop("RUSTXNG_URL").removesuffix("instance/") + "brave"
        with self.assertRaises(SystemExit):
            self.web.run_search("query", 3)
        self.assertEqual(len(self.requests), 1)

    def test_failed_fallback_does_not_loop(self):
        os.environ["BRAVE_API_KEY"] = "brave-key"
        self.web.BRAVE_ENDPOINT = os.environ["RUSTXNG_URL"].removesuffix("instance/") + "brave"
        self.status = 401
        with self.assertRaises(SystemExit):
            self.web.run_search("query", 3)
        self.assertEqual(len(self.requests), 2)

    def test_search_encodes_query_maps_results_and_caps_limit(self):
        os.environ["RUSTXNG_TOKEN"] = "test-token"
        result = self.web.run_search("中文 & Rust", 2)
        self.assertEqual(result, [{"url": "https://example.com", "title": "Example", "snippet": "Snippet"}])
        path, auth = self.requests[0]
        self.assertEqual(auth, "Bearer test-token")
        self.assertEqual(urlsplit(path).path, "/instance/search")
        self.assertEqual(parse_qs(urlsplit(path).query),
                         {"q": ["中文 & Rust"], "format": ["json"], "max_results": ["2"]})
        self.assertEqual(len(self.requests), 1)

    def test_token_is_optional_and_results_are_limited(self):
        self.payload["results"] *= 3
        self.assertEqual(len(self.web.run_search("query", 1)), 1)
        self.assertIsNone(self.requests[0][1])

    def test_empty_results_do_not_trigger_another_request(self):
        self.payload = {"results": []}
        self.assertEqual(self.web.run_search("query", 5), [])
        self.assertEqual(len(self.requests), 1)

    def test_http_errors_and_redirects_do_not_retry(self):
        for status in (401, 500, 302):
            with self.subTest(status=status):
                self.requests.clear()
                self.status = status
                with self.assertRaises(SystemExit):
                    self.web.run_search("query", 5)
                self.assertEqual(len(self.requests), 1)

    def test_invalid_response_exits(self):
        self.payload = {"unexpected": []}
        with self.assertRaises(SystemExit):
            self.web.run_search("query", 5)

    def test_invalid_base_url_is_rejected_before_request(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com", "https://example.com?token=secret"):
            with self.subTest(url=url):
                os.environ["RUSTXNG_URL"] = url
                with self.assertRaises(SystemExit):
                    self.web.run_search("query", 5)
        self.assertEqual(self.requests, [])


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.web = load_web_module()

    def _fetch(self, response: FakeResponse, **kw) -> tuple[str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(self.web.urllib.request, "urlopen", return_value=response), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.web.run_fetch(response.geturl(), timeout=5, max_bytes=65536, raw=False, **kw)
        return stdout.getvalue(), stderr.getvalue()

    def test_html_page_is_converted_and_title_reported(self):
        html = (
            "<html><head><title>Docs</title></head><body>"
            "<h1>API</h1><p>" + "Some real documentation content that is long enough to not be considered a JavaScript shell page. " * 3 + "</p>"
            "</body></html>"
        )
        stdout, stderr = self._fetch(FakeResponse(html.encode()))
        self.assertIn("# API", stdout)
        self.assertIn("Some real documentation content", stdout)
        self.assertIn("[info] title: Docs", stderr)
        self.assertNotIn("[warn]", stderr)

    def test_fetch_main_content_strips_chrome(self):
        html = (
            "<html><head><title>Site</title></head><body>"
            "<nav><a href='/home'>Home</a> <a href='/about'>About</a></nav>"
            "<article><h1>Story</h1>"
            "<p>Body paragraph with enough real substance that it dominates the page and "
            "is kept when fetching with main content extraction enabled.</p>"
            "<a href='https://twitter.com/intent/tweet?url=x'>Share on X</a>"
            "</article></body></html>"
        )
        stdout, stderr = self._fetch(FakeResponse(html.encode()))
        self.assertIn("# Story", stdout)
        self.assertIn("dominates the page", stdout)
        self.assertNotIn("intent/tweet", stdout)
        self.assertNotIn("About", stdout)
        self.assertIn("[info] title: Site", stderr)

    def test_fetch_full_flag_keeps_whole_page(self):
        html = (
            "<html><head><title>Site</title></head><body>"
            "<div><a href='/home'>Home</a></div>"
            "<article><h1>Story</h1>"
            "<p>Body paragraph with enough real substance that it dominates the page and "
            "is kept when fetching with main content extraction enabled.</p>"
            "<a href='https://twitter.com/intent/tweet?url=x'>Share on X</a>"
            "</article></body></html>"
        )
        stdout, _ = self._fetch(FakeResponse(html.encode()), main_content=False)
        self.assertIn("Story", stdout)
        self.assertIn("intent/tweet", stdout)
        self.assertIn("Home", stdout)

    def test_near_empty_page_warns_about_js_rendering(self):
        html = "<html><head><title>App</title></head><body><div id='root'></div></body></html>"
        stdout, stderr = self._fetch(FakeResponse(html.encode()))
        self.assertIn("[warn]", stderr)
        self.assertIn("agent-browser", stderr)
        self.assertIn("--full", stderr)

    def test_non_html_content_passes_through_unconverted(self):
        body = json.dumps({"ok": True}).encode()
        stdout, stderr = self._fetch(
            FakeResponse(body, content_type="application/json", url="https://example.com/api")
        )
        self.assertIn('{"ok": true}', stdout)
        self.assertIn("content-type: application/json", stderr)


if __name__ == "__main__":
    unittest.main()
