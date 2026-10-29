# Last Mile

Kills the last 20% of an almost-finished project.

## Why

Projects ship at 80%: a TODO on the login path, a `console.log` in a
handler, no favicon, a missing 404, a bare `except:` that swallows real
failures. Each item is small. Together they are the difference between
"a demo" and "a product". Last Mile scans the repo for those edges and
drives them closed in priority order, one commit per item, so the finish
is reviewable and the re-scan proves it.

## How it works

1. Scan: `edge_scan.py` walks the repo (respecting `.gitignore`,
   skipping `node_modules`/`dist`/`build`/`vendor`), applies per-language
   heuristics, and emits a prioritized punch list (JSON or markdown).
   Checks: TODO/FIXME/HACK/XXX, placeholder text, unhandled promise
   chains, bare and `except-pass` swallows, missing favicon/meta/OG/
   robots.txt/404/error boundary, console and print debris, dev URLs.
2. Triage: keep the real items, log false positives with a reason.
3. Fix in priority order: high first, one commit per item, named
   `close: <code> in <file> (last-mile)`.
4. Re-scan: the list must shrink monotonically; stop when only low soft
   markers remain or the user stops it.

## Install

Option A: self-installable marketplace.

- Clone or download this repo.
- ZCode: Plugin Marketplace -> Add -> Add Plugin Marketplace.
- Paste the folder path to this repo.
- Install the `last-mile` plugin from the list.

Option B: manual copy.

- Copy this folder into your workspace `plugins/` directory
  (e.g. `~/.zcode/workspace/<name>/plugins/last-mile`).
- Restart the session so the skill loads.

## Try it

```
/last-mile ./my-app high
```

Expected: a prioritized punch list grouped by severity, then a series of
single-item commits that close the high items, ending with a re-scan
report showing the remaining count.

## Requirements

- Python 3 standard library only.
- A project root that is a directory; a `.gitignore` helps but is not
  required.

---

<p align="center">
  <a href="https://z.ai/subscribe?ic=R0K78RJKNW"><img alt="z.ai coding plans - 10% OFF coupon" src="https://img.shields.io/badge/z.ai%20coding%20plans-10%25%20OFF%20coupon-blueviolet" /></a>
  <a href="https://zcode.z.ai/invite/ALWM9JUA"><img alt="Try ZCode free" src="https://img.shields.io/badge/Try%20ZCode-free%20invite-0969da" /></a>
</p>

## License

MIT.
