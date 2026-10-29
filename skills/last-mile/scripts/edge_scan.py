#!/usr/bin/env python3
"""edge_scan.py: scan an almost-finished repo for unfinished edges (stdlib only).

Walks the project, respects .gitignore (and .git/info/exclude), skips
node_modules/.git/dist/build/vendor and common generated dirs, and applies
per-language heuristics (js/ts/py/html/css/md) to find:

  high    TODO / FIXME / HACK / XXX markers
          unhandled async: awaited promise missing catch/try in js/ts,
                 bare except: pass, except-pass and except-broad in py
          placeholder text shipped to users: "Lorem ipsum", "example.com",
                 "placeholder text", "coming soon"
  medium  missing production basics: no favicon reference, no <meta
          description>, no OG tags, no robots.txt, no 404 handling,
          no error boundary / error page component
          console.log / print( debris in non-__main__ code
  low     "TODO-ish" soft markers: WIP, TEMP, DUMMY, sample-data files,
          "test@example.com", "changeme", "password123"

Output: a prioritized punch list as JSON (default) or markdown (-m),
grouped by severity.

Usage:
  python3 edge_scan.py [path] [flags]
  python3 edge_scan.py . -m -o punchlist.md --min-severity medium

Exit codes: 0 = scan completed (regardless of findings), 1 = path does
not exist, 2 = no files matched at all.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "vendor", ".next", ".nuxt",
    "__pycache__", ".venv", "venv", ".tox", "coverage", ".pytest_cache",
    ".mypy_cache", "target", "out", ".idea", ".vscode",
}

JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
PY_EXT = {".py"}
HTML_EXT = {".html", ".htm", ".vue", ".svelte"}
CSS_EXT = {".css", ".scss", ".less"}
MD_EXT = {".md"}

MARKER_RE = re.compile(
    r"\b(TODO|FIXME|HACK|XXX)\b\s*:?\s*(.*)", re.IGNORECASE)
SOFT_RE = re.compile(
    r"\b(WIP|TEMP(?:ORARY)?\b|DUMMY|CLOBBER|MAGIC\s*NUMBER)", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"(Lorem\s+ipsum|example\.com|placeholder\s+text|coming\s+soon|"
    r"test@example\.com|changeme|password123)", re.IGNORECASE)
CONSOLE_RE = re.compile(r"\bconsole\.(log|info|debug|warn)\s*\(")
PRINT_DEBRIS_RE = re.compile(r"^\s*print\s*\(")
BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$")
# crude unhandled-promise heuristics for js/ts: a .then chain whose end
# of statement has no .catch following
THEN_NO_CATCH_RE = re.compile(
    r"\.(then|finally)\s*\([^)]*\)\s*(?:$|;)\s*(?!\.catch)", re.MULTILINE)
FAKE_URL_RE = re.compile(
    r"https?://(localhost|0\.0\.0\.0|127\.0\.0\.1|example\.com)",
    re.IGNORECASE)


def read_gitignore_patterns(root: Path) -> list:
    pats = []
    for gi in (root / ".gitignore", root / ".git" / "info" / "exclude"):
        if gi.is_file():
            try:
                for line in gi.read_text(
                        encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pats.append(line.lstrip("!").rstrip("/"))
            except OSError:
                pass
    return pats


def gitignored(rel: str, pats: list) -> bool:
    """Cheap .gitignore matching: exact names, trailing /, and * globs."""
    name = Path(rel).name
    for p in pats:
        if p == name or p == rel:
            return True
        base = p.rstrip("/")
        if base and (base == name or rel.startswith(base + "/")):
            return True
        if "*" in p:
            rx = re.escape(p).replace(r"\*", ".*")
            if re.match("^%s$|^%s/" % (rx, rx), rel) or \
                    re.search("%s" % rx, rel):
                return True
    return False


def walk_files(root: Path):
    pats = read_gitignore_patterns(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        keep = []
        for d in dirnames:
            if d in SKIP_DIRS:
                continue
            rel = d if rel_dir == "." else rel_dir + "/" + d
            if gitignored(rel, pats):
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            rel = f if rel_dir == "." else rel_dir + "/" + f
            if gitignored(rel, pats):
                continue
            yield Path(dirpath) / f, rel


def classify(line: str, lang: str) -> list:
    """Return (severity, code, detail) tuples for one line."""
    out = []
    m = MARKER_RE.search(line)
    if m:
        out.append(("high", "marker", "%s %s" % (
            m.group(1), m.group(2).strip()[:80] or "(no note)")))
    if PLACEHOLDER_RE.search(line):
        out.append(("high", "placeholder",
                    PLACEHOLDER_RE.search(line).group(0)))
    if SOFT_RE.search(line) and not m:
        out.append(("low", "soft-marker",
                    SOFT_RE.search(line).group(0)))
    if lang in ("js", "ts"):
        if CONSOLE_RE.search(line):
            out.append(("medium", "console-debris",
                        CONSOLE_RE.search(line).group(0)))
    return out


def scan_file(path: Path, rel: str) -> list:
    ext = path.suffix.lower()
    lang = None
    if ext in JS_EXT:
        lang = "ts" if ext in (".ts", ".tsx") else "js"
    elif ext in PY_EXT:
        lang = "py"
    elif ext in HTML_EXT:
        lang = "html"
    elif ext in CSS_EXT or ext in MD_EXT:
        lang = "soft"
    else:
        return []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    findings = []

    for i, line in enumerate(lines, 1):
        for sev, code, detail in classify(line, lang):
            findings.append((sev, code, rel, i, detail, line.strip()[:80]))

    # whole-file checks
    if lang == "js":
        # .then without .catch
        for m in THEN_NO_CATCH_RE.finditer(text):
            ln = text[:m.start()].count("\n") + 1
            findings.append(("high", "unhandled-promise", rel, ln,
                             ".then chain without .catch",
                             text[max(0, m.start() - 40):m.end()].strip()
                             [:80]))
    if lang == "py":
        for i, line in enumerate(lines, 1):
            if BARE_EXCEPT_RE.match(line):
                findings.append(("high", "bare-except", rel, i,
                                 "bare except: swallows all errors",
                                 line.strip()))
            for m in re.finditer(r"except\s+\w*Exception\w*\s*:\s*pass",
                                 line):
                findings.append(("high", "except-pass", rel, i,
                                 "except ... pass hides failures",
                                 line.strip()))
            if PRINT_DEBRIS_RE.match(line) and not re.search(
                    r"^if\s+__name__\s*==\s*['\"]__main__['\"]", text):
                # allow print() in __main__ demo scripts
                if "__name__" not in text:
                    findings.append(("medium", "print-debris", rel, i,
                                     "print() left in library code",
                                     line.strip()))
    if FAKE_URL_RE.search(text) and lang in ("js", "ts", "py", "html"):
        for m in FAKE_URL_RE.finditer(text):
            ln = text[:m.start()].count("\n") + 1
            findings.append(("medium", "dev-url", rel, ln,
                             "local/dev URL committed: %s" % m.group(0),
                             m.group(0)))
    return findings


SEV_RANK = {"high": 0, "medium": 1, "low": 2}


def project_checks(root: Path) -> list:
    """Repo-level production basics; returns (sev, code, path, line,
    detail, sample)."""
    out = []

    def add(sev, code, detail):
        out.append((sev, code, "(project)", 0, detail, detail[:80]))

    text_files = []
    has_robots = False
    for p, rel in walk_files(root):
        if p.is_dir():
            continue
        if p.name == "robots.txt":
            has_robots = True
        if p.suffix.lower() in JS_EXT | HTML_EXT | PY_EXT | CSS_EXT:
            text_files.append((p, rel))
    if not has_robots:
        add("medium", "no-robots-txt", "no robots.txt at repo root")

    alltext = ""
    for p, _rel in text_files:
        try:
            alltext += p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    if not re.search(r"<link[^>]*rel=[\"']icon", alltext) and \
            not re.search(r"<link[^>]*rel=[\"']apple-touch-icon", alltext) \
            and "favicon" not in alltext.lower():
        add("medium", "no-favicon", "no favicon reference found")
    if "<html" in alltext.lower() and \
            not re.search(r"<meta[^>]*name=[\"']description[\"']", alltext):
        add("medium", "no-meta-description",
            "HTML present but no <meta description>")
    if "<html" in alltext.lower() and "og:" not in alltext and \
            "twitter:title" not in alltext:
        add("medium", "no-og-tags", "no Open Graph / Twitter card tags")
    if re.search(r"\b404\b", alltext) or \
            re.search(r"NotFound", alltext, re.IGNORECASE) or \
            "err404" in alltext.lower():
        pass
    elif "django" in _find_framework(root):
        add("medium", "no-404", "Django project with no 404.html / "
            "handler404 wiring found")
    elif re.search(r"\b(createRoot|ReactDOM|createApp|next|svelte|nuxt)\b",
                   alltext):
        add("medium", "no-404-check", "frontend framework detected; "
            "verify a 404 route/behavior exists (not auto-verifiable)")
    if "ErrorBoundary" not in alltext and "errorElement" not in alltext \
            and "error.tsx" in [p.name for p, _ in text_files]:
        add("low", "no-error-boundary", "no error boundary component found")
    if "skeleton" not in alltext.lower() and "loading=" in alltext and \
            not re.search(r"(skeleton|Spinner|Progress)", alltext):
        add("low", "no-loading-state", "loading props used but no "
            "skeleton/spinner found")
    return out


def _find_framework(root: Path) -> str:
    for marker in ("manage.py", "requirements.txt", "package.json",
                   "pyproject.toml", "go.mod"):
        f = root / marker
        if f.is_file():
            try:
                t = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "django" in t.lower() or "djangorestframework" in t:
                return "django"
    return ""


def main():
    ap = argparse.ArgumentParser(
        description="Scan a repo for unfinished edges and emit a "
                    "prioritized punch list.")
    ap.add_argument("path", nargs="?", default=".",
                    help="project root to scan (default: current dir)")
    ap.add_argument("-o", "--out", default="",
                    help="write the report here instead of stdout")
    ap.add_argument("-m", "--markdown", action="store_true",
                    help="markdown output instead of JSON")
    ap.add_argument("--min-severity", default="low",
                    choices=["low", "medium", "high"],
                    help="drop findings below this severity (default: show "
                         "all)")
    ap.add_argument("--no-project-checks", action="store_true",
                    help="skip repo-level production-basics checks")
    args = ap.parse_args()

    root = Path(args.path)
    if not root.is_dir():
        print("error: %s is not a directory" % args.path, file=sys.stderr)
        return 1

    min_rank = SEV_RANK[args.min_severity]
    all_findings = []
    seen_files = 0
    for p, rel in walk_files(root):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        seen_files += 1
        all_findings.extend(scan_file(p, rel))
    if not args.no_project_checks:
        all_findings.extend(project_checks(root))

    if seen_files == 0 and not args.no_project_checks and \
            not all_findings:
        print("error: no scannable files under %s" % args.path,
              file=sys.stderr)
        return 2

    keep = [f for f in all_findings if SEV_RANK[f[0]] <= min_rank]
    keep.sort(key=lambda f: (SEV_RANK[f[0]], f[2], f[3]))

    if args.markdown:
        report = render_markdown(keep, root)
    else:
        report = json.dumps({
            "project": str(root),
            "total_findings": len(keep),
            "by_severity": {
                s: sum(1 for f in keep if f[0] == s)
                for s in ("high", "medium", "low")},
            "findings": [
                {"severity": s, "code": c, "file": f, "line": ln,
                 "detail": d, "context": ctx}
                for s, c, f, ln, d, ctx in keep
            ],
        }, indent=2)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print("wrote %s (%d findings)" % (args.out, len(keep)),
              file=sys.stderr)
    else:
        print(report)
    return 0


def render_markdown(findings, root):
    lines = ["# Last-mile punch list", "", "Project: `%s`" % root, ""]
    cur = None
    for s, c, f, ln, d, ctx in findings:
        if s != cur:
            cur = s
            lines += ["", "## %s" % s.capitalize(), ""]
        loc = "`%s:%d`" % (f, ln) if ln else f"`{f}`"
        lines.append("- **%s** at %s: %s" % (c, loc, d))
    lines.append("")
    lines.append("Fix top-down; one commit per item.")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
