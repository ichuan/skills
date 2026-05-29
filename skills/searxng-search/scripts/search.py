#!/usr/bin/env python3
"""
SearXNG search CLI.

Usage:
    search.py <query> [--page N] [--limit N]

Config (highest priority first):
    1. Environment variables (SEARXNG_URL, SEARXNG_TOKEN)
    2. .env file in the current working directory
    3. Built-in defaults

    SEARXNG_URL    - SearXNG instance base URL (default: https://search.981234.xyz)
    SEARXNG_TOKEN  - Bearer auth token (default: empty / no auth)

Output: NDJSON, one result per line: {"url": ..., "title": ..., "snippet": ...}
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error


DEFAULT_URL = "https://search.981234.xyz"


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


def search(query: str, base_url: str, token: str | None, pageno: int = 1) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "format": "json", "pageno": pageno})
    url = f"{base_url.rstrip('/')}/search?{params}"

    req = urllib.request.Request(url)
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

    results = []
    for r in data.get("results", []):
        results.append({
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
        })
    return results


def main():
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Search via SearXNG")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--limit", type=int, default=10, help="Max results to output (default: 10)")
    args = parser.parse_args()

    base_url = os.environ.get("SEARXNG_URL", DEFAULT_URL)
    token = os.environ.get("SEARXNG_TOKEN") or None

    results = search(args.query, base_url, token, args.page)
    for r in results[: args.limit]:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
