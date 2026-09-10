# Web Fetch

Reference skill for reading web pages with `trafilatura`. Replaces the
built-in WebFetch tool, which is denied by managed settings in claude-env
containers.

## Invisible Knowledge

### Why WebFetch Is Disabled

WebFetch downloads a page, converts it to markdown, then runs a small fast
model over it against the caller's prompt. The session only ever sees that
model's summary. For code and documentation work that loses exact wording,
version numbers, and code samples. It also cannot be pointed at a different
extractor. The claude-env images deny the tool in
`/etc/claude-code/managed-settings.json` so the choice is uniform across every
variant and cannot be toggled back from a project settings file.

### Why trafilatura

Alternatives considered:

- `curl | pandoc -f html -t markdown`: converts the whole page, including
  navigation and footers. No boilerplate removal.
- Readability ports: extraction only, no download, no crawling, no feed or
  sitemap discovery.
- trafilatura: download plus boilerplate removal plus metadata, with feed,
  sitemap, and crawl modes in one CLI. Widely used for corpus building, so
  extraction quality is well exercised.

### Why Documentation-Only

The tool is a CLI with stable flags. A wrapper script would only re-encode
flags the LLM can read from `SKILL.md`, and would need to live in the container
image rather than this repo. Shell recipes compose with `grep`, `head`, and
`sed` for free.

### Trade-off Accepted

Full page text enters context instead of a summary. The Context Discipline
section in `SKILL.md` exists because of this: write to `/tmp`, then read
selectively. Neither WebFetch nor trafilatura renders JavaScript, so nothing is
lost on that axis.

### Known Limits Found in Testing

- trafilatura identifies itself with its own user agent, and spiegel.de
  answers 403 to it while serving curl and browsers. trafilatura 2.x only
  reads `USER_AGENTS` from a config that differs from its built-in default,
  so a config file cannot fix plain CLI use or feed, sitemap, and crawl
  discovery. The claude-env base image therefore rewrites the one line of
  the installed package that sets the default header, verifies it by import,
  and fails the build if upstream moves it. `SKILL.md` keeps the curl pipe
  as the fallback for stale or unpatched images.
- `--archived` returned a months-old homepage snapshot for spiegel.de. It is a
  fallback of last resort, not a transparent retry.

### Dependency

The command exists on PATH only because the claude-env base image installs it
into `/opt/cli-tools/.venv`. Outside those containers the `uvx` fallback in
`SKILL.md` runs it from a temporary environment.
