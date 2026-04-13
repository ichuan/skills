---
name: searxng-search
description: Web search via a self-hosted SearXNG aggregation server. Use when the user asks to search the web, find URLs, look up information online, or research a topic using a search engine. Returns URL, title, and snippet for each result.
---

# SearXNG Search

Use `scripts/search.py` to perform web searches and return structured results.

## Configuration

Configuration is resolved in the following priority order:

1. **Environment variables** (highest priority)
2. **`.env` file** in the current working directory (auto-loaded if present)
3. **Built-in defaults**

| Env var         | Purpose                          | Default                        |
|-----------------|----------------------------------|--------------------------------|
| `SEARXNG_URL`   | Base URL of SearXNG instance     | `https://search.981234.xyz`    |
| `SEARXNG_TOKEN` | Bearer token for auth (optional) | *(empty = no auth header sent)*|

Example `.env`:

```
SEARXNG_URL=https://search.example.com
SEARXNG_TOKEN=your-secret-token
```

## Usage

```bash
# Basic search (uses defaults)
python3 scripts/search.py "query"

# Paginate or limit
python3 scripts/search.py "query" --page 2 --limit 5

# Custom instance with auth
SEARXNG_URL=https://my.instance.com SEARXNG_TOKEN=my-token python3 scripts/search.py "query"
```

## Output format

NDJSON — one JSON object per line:

```json
{"url": "https://example.com", "title": "Page Title", "snippet": "Relevant excerpt..."}
```

## Workflow

1. Run the script, capturing stdout.
2. Parse NDJSON lines into a list of results.
3. Present to the user as a numbered list of links with snippets.
4. If the user wants more results, re-run with `--page N` or a higher `--limit`.

## Notes

- Default limit is 10; one server page typically returns ~40 results.
- If `SEARXNG_TOKEN` is unset or empty, the `Authorization` header is omitted (public instances).
- Script exits with code 1 and prints to stderr on HTTP or network failure.
