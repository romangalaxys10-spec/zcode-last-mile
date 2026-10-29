---
name: last-mile
description: Use when a project is roughly 80% done and needs to be finished for real: unfinished markers, missing states, production basics, leftover debug debris. Scan, get a prioritized punch list, then close the items one commit at a time.
---

# last-mile

Close the last 20% of an almost-finished project.

## Inputs

- `path`: the project root. Default: current directory.
- `min-severity`: `high` (markers, unhandled promises, bare excepts,
  placeholder text), `medium` (production basics, console/print debris,
  dev URLs), or `low` (everything, including soft WIP/dummy markers).
  Default `low`.

## Workflow

### 1. Scan

```bash
python3 scripts/edge_scan.py <path> --min-severity low
```

The script is stdlib-only. It walks the repo, respects `.gitignore` and
`.git/info/exclude`, skips `node_modules`, `.git`, `dist`, `build`,
`vendor`, `.next`, `__pycache__`, venvs, and similar generated dirs.
It applies per-language heuristics (js/ts, py, html) and emits a JSON
punch list grouped by severity, highest first. For a human-readable board
use `-m`:

```bash
python3 scripts/edge_scan.py <path> -m -o last-mile/punchlist.md
```

Read the report. Do not start fixing before the list exists.

### 2. Triage

- Keep every `high` item: these are shipped defects (user-visible
  placeholder text, swallowed exceptions, TODOs on critical paths).
- Keep `medium` items that sit on a user-facing surface.
- Drop false positives and note them in `last-mile/triage.md` with a
  one-line reason, so a later run can skip them.

### 3. Fix in priority order

- One item per commit. Commit message: `close: <code> in <file> (last-mile)`.
- Order: high first (markers on critical paths, placeholder text,
  unhandled promises, bare excepts), then medium (production basics,
  console/print debris, dev URLs), then low (soft markers, missing
  loading states, error boundary gaps).
- For missing production basics the scanner reports:
  - no favicon: add a `favicon.ico` plus the `<link rel="icon">` tag,
  - no meta description: add a real one per page, not a copy of the title,
  - no OG tags: add `og:title`, `og:description`, `og:image`,
    `twitter:card`,
  - no robots.txt: add one, allow-all plus the sitemap line if a sitemap
    exists,
  - no 404: wire a real not-found page or route; the scanner flags "no
    404 handling" as a check, not a certainty, so verify it,
  - no error boundary: add one around the route/component level for
    React (class or `errorElement` in react-router / Next), a top-level
    `catchErrorBoundary` in Svelte, or an error page for Vue.

### 4. Re-scan and verify

```bash
python3 scripts/edge_scan.py <path> --min-severity medium
```

The list must shrink monotonically. If a previously closed item
reappears, the fix was wrong; re-open it. Stop when only
`low` soft markers remain or the user says stop.

## Honest limits

- Heuristics are per-language regexes, not a type checker. A
  `promise.then()` split across lines will not be caught; a `.catch`
  on the next line reads as handled.
- "No 404 / no error boundary" items are detection-of-absence checks
  over committed text. A 404 implemented in server config or a
  framework default is invisible to the scan; verify before claiming
  it is missing.
- The scanner reads at most 2 MB per file; huge generated bundles
  are skipped on size as well.
- Respecting `.gitignore` is best-effort pattern matching, not the
  full gitignore semantics; a pattern using `!` negation or `**`
  wildcards may be read as a simple `*` glob.

## Guardrails

- Never delete a `TODO` to silence the scan. Resolve it or rewrite it
  as an issue with an owner.
- Do not bulk-fix `console.log` by greping them out; check each call
  is not the only log line in a handler.
- One commit per item keeps the re-scan diff readable and the bisect
  honest.
- After the loop, print the final count by severity so the user sees
  where the project stands.
