---
name: web-search-fetch
description: Web search and URL fetch for AI agents. Use when the user asks to search the web, find URLs, research a topic, or read/fetch/summarize a webpage as clean Markdown. The search backend is configurable and invisible to the caller; fetching uses plain HTTP plus a local HTML-to-Markdown converter with zero dependencies.
---

# Web Search & Fetch

Run the commands from the skill directory, the directory containing this file:

```bash
cd path/to/web-search-fetch
python3 scripts/web.py search "python 3.13 release notes" --limit 5
```

On Windows, use the equivalent path syntax:

```powershell
cd path\to\web-search-fetch
py scripts\web.py search "python 3.13 release notes" --limit 5
```

The script has two subcommands:

- `search <query>` — web search, prints one JSON result per line: `{"url", "title", "snippet"}`
- `fetch <url>` — fetch a URL and print the page as Markdown (title and warnings go to stderr)

The user never needs to know which search backend is in use; both subcommands take plain queries/URLs.

## Search

- Output is NDJSON; each line is one result with `url`, `title`, `snippet`.
- `--limit N` caps the number of results (default 8, max 20).

## Fetch

```bash
python3 scripts/web.py fetch https://www.example.com/news/story
```
- By default only the **main content** is kept: the converter locates the article body and drops navigation, share links, related/popular lists, promos, cookie banners and hidden elements. Headings, paragraphs, lists, code blocks, links, images and tables are preserved, and relative URLs are resolved against the final page URL.
- `--full` converts the whole page instead. Main-content extraction assumes an article-style page; on list/index pages (homepages, category feeds, link directories) it can prune the headline list too. If the output looks too short or is missing what you came for, judge from the content and retry once with `--full`.
- `--raw` prints the unconverted response body (useful for JSON/plain-text endpoints).
- `--timeout N` (default 30s) and `--max-bytes N` (default 5 MB) bound the request.
- Conversion is done by the local `scripts/html2markdown.py` module (stdlib only, no pip install).

## JavaScript-rendered pages

Plain HTTP cannot run JavaScript. When `fetch` extracts almost no text it prints a `[warn]` line telling you the page likely needs JS rendering (the line also suggests `--full`). Try `--full` once; if the full page is also nearly empty, do not retry further — switch to the **agent-browser** skill and load the URL in a real browser instead.

## Configuration

Read from environment variables, falling back to a `.env` file in the current working directory:

```
# .env (project root)
WEBSEARCH_PROVIDER=brave
WEBSEARCH_API_KEY=your-key
```

- `WEBSEARCH_PROVIDER` — search backend, currently `brave` (default). Adding a backend means adding one provider function in `web.py`; callers and this document do not change.
- `WEBSEARCH_API_KEY` — API key for the active provider (`BRAVE_API_KEY` is also accepted for brave).

Fetch needs no configuration.
