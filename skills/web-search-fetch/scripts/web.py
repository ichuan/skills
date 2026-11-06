#!/usr/bin/env python3
"""
Web search + URL fetch CLI.

Usage:
    web.py search <query> [--limit N]
    web.py fetch <url> [--timeout N] [--max-bytes N] [--raw]

Config (highest priority first):
    1. Environment variables
    2. .env file in the current working directory

    BRAVE_API_KEY     - Brave API key (preferred provider when set)
    WEBSEARCH_API_KEY - legacy alias for BRAVE_API_KEY
    RUSTXNG_URL       - RustXNG instance base URL, used when no Brave key is set
    RUSTXNG_TOKEN     - optional RustXNG Bearer token

Output:
    search: NDJSON, one result per line: {"url": ..., "title": ..., "snippet": ...}
    fetch:  page content converted to Markdown (or raw body with --raw)

HTML conversion: noise subtrees (nav, script, footer, ...) are stripped by a
stdlib HTMLParser filter, then the local html2markdown module (same directory)
converts the remaining HTML to Markdown. Zero third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html import escape as html_escape, unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from html2markdown import html2markdown  # noqa: E402  (local module)

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_LIMIT = 8
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_BYTES = 5 * 1024 * 1024

# Below this many characters of extracted text, assume the page needs JS rendering.
MIN_CONTENT_CHARS = 200

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 web-search-fetch"
)

# Tags whose entire subtree is noise for LLM consumption.
NOISE_TAGS = {
    "head", "script", "style", "noscript", "template", "svg", "iframe",
    "nav", "aside", "footer", "form", "button", "select", "option",
}


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from .env in CWD into os.environ (only if not already set)."""
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            # Strip optional surrounding quotes
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _configure_output_encoding() -> None:
    """Keep CLI output UTF-8 even when Windows inherits a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _die(message: str, code: int = 1) -> None:
    print(f"[error] {message}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def brave_search(query: str, limit: int) -> list[dict]:
    api_key = os.environ.get("BRAVE_API_KEY") or os.environ.get("WEBSEARCH_API_KEY")
    if not api_key:
        _die(
            "WEBSEARCH_API_KEY (or BRAVE_API_KEY) is not set. "
            "Export it or put it in .env in the working directory."
        )

    params = urllib.parse.urlencode({"q": query, "count": min(limit, 20)})
    req = urllib.request.Request(
        f"{BRAVE_ENDPOINT}?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in {402, 429}:
            raise
        _die(f"Brave search HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        _die(f"Brave search request failed: {e.reason}")

    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("description", ""),
        })
        if len(results) >= limit:
            break
    return results


class _NoSearchRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a private instance's credentials to a redirect target.
        return None


def rustxng_search(query: str, limit: int) -> list[dict]:
    base_url = os.environ.get("RUSTXNG_URL", "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        _die("RUSTXNG_URL must be an HTTP(S) base URL without credentials, query or fragment.")

    params = urllib.parse.urlencode({"q": query, "format": "json", "max_results": min(limit, 20)})
    headers = {"Accept": "application/json"}
    token = os.environ.get("RUSTXNG_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{base_url}/search?{params}", headers=headers)
    opener = urllib.request.build_opener(_NoSearchRedirects())
    try:
        with opener.open(req, timeout=DEFAULT_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        _die(f"RustXNG search HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        _die(f"RustXNG search request failed: {e.reason}")
    except (ValueError, UnicodeDecodeError):
        _die("RustXNG search returned invalid JSON.")

    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        _die("RustXNG search response must contain a results list.")
    results = []
    for r in data["results"][:limit]:
        if not isinstance(r, dict):
            _die("RustXNG search returned an invalid result.")
        results.append({
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
        })
    return results


def run_search(query: str, limit: int) -> list[dict]:
    if os.environ.get("BRAVE_API_KEY") or os.environ.get("WEBSEARCH_API_KEY"):
        try:
            return brave_search(query, limit)
        except urllib.error.HTTPError as e:
            if not os.environ.get("RUSTXNG_URL", "").strip():
                _die(f"Brave search HTTP {e.code}: {e.reason}; RUSTXNG_URL is not set.")
            print(f"[warn] Brave search HTTP {e.code}; falling back to RustXNG.", file=sys.stderr)
            return rustxng_search(query, limit)
    if os.environ.get("RUSTXNG_URL", "").strip():
        return rustxng_search(query, limit)
    _die("Set BRAVE_API_KEY or RUSTXNG_URL in the environment or .env in the working directory.")


# ---------------------------------------------------------------------------
# Fetch: HTML -> Markdown
# ---------------------------------------------------------------------------

class NoiseFilter(HTMLParser):
    """Drop non-content subtrees and re-emit the remaining HTML unchanged."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip_depth = 0

    def _attrs(self, attrs: list[tuple[str, str | None]]) -> str:
        parts = []
        for key, value in attrs:
            if value is None:
                parts.append(key)
            else:
                parts.append(f'{key}="{html_escape(value, quote=True)}"')
        return (" " + " ".join(parts)) if parts else ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in NOISE_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        self._out.append(f"<{tag}{self._attrs(attrs)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in NOISE_TAGS or self._skip_depth:
            return
        self._out.append(f"<{tag}{self._attrs(attrs)} />")

    def handle_endtag(self, tag: str) -> None:
        if tag in NOISE_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._out.append(html_escape(data, quote=False))

    # Comments, doctypes, processing instructions and CDATA are dropped.
    def handle_comment(self, data: str) -> None:
        pass

    def handle_decl(self, decl: str) -> None:
        pass

    def unknown_decl(self, data: str) -> None:
        pass

    def handle_pi(self, data: str) -> None:
        pass

    def output(self) -> str:
        return "".join(self._out)


def html_to_markdown(html_text: str, base_url: str = "", main_content: bool = False) -> tuple[str, str]:
    """Return (title, markdown) for an HTML document."""
    title = ""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if match:
        title = html_unescape(match.group(1)).strip()

    if main_content:
        # The extractor needs the full tree (head title, header h1, nav/footer
        # containers it prunes itself); pre-filtering would starve it.
        return title, html2markdown(html_text, base_url=base_url, main_content=True)

    noise_filter = NoiseFilter()
    noise_filter.feed(html_text)
    noise_filter.close()

    return title, html2markdown(noise_filter.output(), base_url=base_url)


# ---------------------------------------------------------------------------
# Fetch: HTTP
# ---------------------------------------------------------------------------

def _decode(body: bytes, content_type: str) -> str:
    charset = None
    match = re.search(r"charset=([\w.:-]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1)
    if not charset:
        # HTML pages often declare their encoding in a <meta> tag near the top.
        probe = body[:4096].decode("ascii", errors="ignore")
        meta = re.search(r'charset=["\']?([\w.:-]+)', probe, re.IGNORECASE)
        if meta:
            charset = meta.group(1)
    for cs in (charset, "utf-8", "latin-1"):
        if not cs:
            continue
        try:
            return body.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def run_fetch(url: str, timeout: int, max_bytes: int, raw: bool, main_content: bool = True) -> None:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        # urllib does not decompress compressed responses; ask for identity.
        "Accept-Encoding": "identity",
        "Accept-Language": "en,zh;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read(max_bytes)
            final_url = resp.geturl()
    except urllib.error.HTTPError as e:
        _die(f"fetch HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        _die(f"fetch failed: {e.reason}")
    except ValueError as e:
        _die(f"invalid URL: {e}")

    if final_url != url:
        print(f"[info] redirected to: {final_url}", file=sys.stderr)

    is_html = "html" in content_type.lower() or (
        not content_type and body[:512].lstrip().lower().startswith(b"<!doctype html")
    )

    if raw or not is_html:
        print(_decode(body, content_type))
        print(
            f"[info] content-type: {content_type or 'unknown'}, {len(body)} bytes",
            file=sys.stderr,
        )
        return

    title, markdown = html_to_markdown(
        _decode(body, content_type), base_url=final_url, main_content=main_content
    )
    print(markdown)
    if title:
        print(f"[info] title: {title}", file=sys.stderr)
    if len(re.sub(r"\s", "", markdown)) < MIN_CONTENT_CHARS:
        hint = " Retry with `--full` for the whole page." if main_content else ""
        print(
            "[warn] extracted content is very short; the page likely needs JavaScript "
            "rendering. Use the agent-browser skill to load it in a real browser." + hint,
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    _configure_output_encoding()
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Web search + URL fetch")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="web search -> NDJSON results")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=DEFAULT_LIMIT)

    p_fetch = sub.add_parser("fetch", help="URL -> Markdown")
    p_fetch.add_argument("url")
    p_fetch.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p_fetch.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    p_fetch.add_argument(
        "--raw", action="store_true",
        help="output the raw response body without HTML conversion",
    )
    p_fetch.add_argument(
        "--full", action="store_true",
        help="convert the whole page instead of only the main content",
    )

    args = parser.parse_args()

    if args.command == "search":
        for result in run_search(args.query, args.limit):
            print(json.dumps(result, ensure_ascii=False))
        return

    run_fetch(args.url, args.timeout, args.max_bytes, args.raw, main_content=not args.full)


if __name__ == "__main__":
    main()
