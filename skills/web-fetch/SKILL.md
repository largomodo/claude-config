---
name: web-fetch
description: Read or fetch a URL / web page as markdown with trafilatura. Use whenever a task needs the content of a web page, article, or documentation URL. The built-in WebFetch tool is disabled in claude-env containers; this is its replacement.
---

# Web Fetch

Fetch a web page and extract its main content with `trafilatura`. Output is
markdown produced locally; no summarizing model sits between the page and you.

## Prerequisite

```bash
command -v trafilatura || echo "not installed"
```

Inside claude-env containers it is on PATH (cli-tools venv). Elsewhere, run it
without installing:

```bash
uvx trafilatura -u <url> --markdown
```

## Basic Fetch

```bash
trafilatura -u <url> --markdown
```

Extracts the main text, drops navigation, headers, footers, and boilerplate.

## Options

| Flag                   | Effect                                                    |
| ---------------------- | --------------------------------------------------------- |
| `--precision`          | Less noise, possibly less text                            |
| `--recall`             | More text, possibly more noise (try when output is short) |
| `--links`              | Keep hyperlinks with targets                              |
| `--formatting`         | Keep bold/italic                                          |
| `--no-comments`        | Drop comment sections                                     |
| `--no-tables`          | Drop tables                                               |
| `--with-metadata`      | Add title, author, date, URL (best with `--json`)         |
| `--json`               | JSON instead of markdown (`--output-format` for others)   |
| `--target-language xx` | Only keep documents in language `xx` (ISO 639-1)          |
| `--archived`           | Fall back to the Internet Archive if the download fails   |
| `-f`                   | Fast mode, no fallback extraction algorithms              |

## Multiple Pages

```bash
# Preview URLs without downloading
trafilatura --sitemap <site-url> --list
trafilatura --feed <site-or-feed-url> --list

# Fetch every URL discovered, only paths containing a pattern
trafilatura --sitemap <site-url> --url-filter /docs/ --markdown -o /tmp/site

# Crawl N pages starting from a URL
trafilatura --crawl 10 -u <url> --markdown -o /tmp/site

# Batch from a file, one URL per line
trafilatura -i urls.txt --markdown -o /tmp/pages
```

## Non-HTML Content

| Content        | Command                                                   |
| -------------- | --------------------------------------------------------- |
| PDF            | `curl -sL <url> -o /tmp/doc.pdf && pdftotext -layout /tmp/doc.pdf -` |
| JSON API       | `http <url>` (httpie) or `curl -sL <url> \| jq .`         |
| Raw file       | `curl -sL <url>`                                          |

## Context Discipline

Unlike WebFetch, nothing summarizes the page for you. A full article is often
tens of KB. Write to a file first, then read what you need:

```bash
trafilatura -u <url> --markdown > /tmp/page.md
wc -c /tmp/page.md
grep -n -i "<keyword>" /tmp/page.md
sed -n '1,80p' /tmp/page.md
```

Read the whole file only when it is small or the task needs all of it.

## When the Server Returns 403

claude-env images set trafilatura's default user agent to the current Chrome
release at build time, so plain fetches, feeds, and sitemaps already pass
user-agent bot blocks. Confirm what the image is sending:

```bash
trafilatura-ua.sh --check "$(dirname "$(command -v trafilatura)")/python"
```

If that prints `trafilatura/...`, the image was built without the patch. If it
prints an old Chrome major, the image is stale. Either way, download with curl
and a fresh user agent, then let trafilatura extract:

```bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'
curl -sL -A "$UA" <url> | trafilatura --markdown
```

Bump the Chrome major if that still returns a block page. A persistent 403
with any user agent is a real bot block; report it to the user.

## When Output Is Empty or Truncated

1. Retry with `--recall`.
2. Retry with `--archived`. The Internet Archive copy may be stale; check its
   date before trusting it.
3. Check the raw HTML: `curl -sL <url> | head -c 2000`. A near-empty body or a
   challenge page means a bot block or a JavaScript-only page. trafilatura does
   not execute JavaScript. Report this to the user instead of retrying further.

Front pages and index pages extract to a few teasers only; that is expected.
Fetch the article URLs instead.

## When NOT to Use

- Searching the web: use WebSearch, which stays enabled.
- Calling a JSON API: use httpie or curl directly.
- Local files: use Read.
