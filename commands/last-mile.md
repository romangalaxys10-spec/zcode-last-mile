---
description: Scan an almost-finished project for unfinished edges (markers, missing states, production basics, debug debris) and close them one commit at a time.
allowed-tools: Read, Bash, Write, Edit, Grep, Glob
argument-hint: [path] [min-severity: high|medium|low]
---
Invoke the `last-mile` skill with this input: **$ARGUMENTS**

Args: the project path (default the current directory) and an optional
minimum severity to start from.

If args are empty:
- scan the current directory with `edge_scan.py` at severity low;
- triage the punch list, keeping high items and user-facing medium items;
- fix items top-down, one commit per item, then re-scan until the list
  only carries low soft markers or the user stops it.
