#!/usr/bin/env python3
"""
crawl4ai-fetch CLI — convert any URL to clean Markdown via a self-hosted crawl4ai server.

Usage:
    crawl.py <url> [--filter fit|raw|bm25] [--query TEXT]

Config (highest priority first):
    1. Environment variables (CRAWL4AI_URL, CRAWL4AI_TOKEN)
    2. .env file in the current working directory (auto-loaded if present)
    3. Built-in defaults

    CRAWL4AI_URL    - Base URL of crawl4ai instance  (default: https://crawl.981234.xyz)
    CRAWL4AI_TOKEN  - Bearer auth token (optional)   (default: empty / no auth)

Output: the fetched page as Markdown, printed to stdout.
        On error: message on stderr, exit code 1.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


DEFAULT_URL = "https://crawl.981234.xyz"


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
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def fetch_markdown(url: str, base_url: str, token: str | None,
                   filter_mode: str = "fit", query: str | None = None) -> str:
    endpoint = f"{base_url.rstrip('/')}/md"
    payload = json.dumps({
        "url": url,
        "f": filter_mode,
        "q": query,
        "c": "0",  # always fetch fresh; cache returns empty if URL not yet cached
    }).encode()

    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[error] HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[error] Request failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if not data.get("success"):
        print(f"[error] Server returned success=false for {url}", file=sys.stderr)
        sys.exit(1)

    return data.get("markdown", "")


def main():
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Fetch a URL as Markdown via crawl4ai")
    parser.add_argument("url", help="URL to fetch and convert")
    parser.add_argument(
        "--filter",
        dest="filter_mode",
        default="fit",
        choices=["fit", "raw", "bm25"],
        help="Content filter mode (default: fit)",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Optional relevance query for bm25 filter mode",
    )
    args = parser.parse_args()

    base_url = os.environ.get("CRAWL4AI_URL", DEFAULT_URL)
    token = os.environ.get("CRAWL4AI_TOKEN") or None

    markdown = fetch_markdown(
        args.url,
        base_url,
        token,
        filter_mode=args.filter_mode,
        query=args.query,
    )
    print(markdown)


if __name__ == "__main__":
    main()
