#!/usr/bin/env python3
"""Render recently starred repositories into README.md, between the STARRED markers.

The workflow has called this path since March and the file never existed -- it was
committed as `update-readme.py`, empty, while the workflow ran `update_readme.py`.
Every scheduled run since has failed. This is that script, under the name the
workflow actually invokes.

Writes nothing unless the rendered block differs, so an unchanged sweep produces no
commit and no noise.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

USER = os.environ.get("GITHUB_USER", "ahmadrashad1")
COUNT = int(os.environ.get("STAR_COUNT", "6"))
README = pathlib.Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- STARRED:START -->", "<!-- STARRED:END -->"

# Fixed width so the monospace frame stays square however long a repository name
# is -- a ragged right edge is the one thing this layout cannot absorb.
WIDTH = 78


def fetch_starred() -> list[dict]:
    url = f"https://api.github.com/users/{USER}/starred?per_page={COUNT}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.star+json",
            "User-Agent": f"{USER}-profile-readme",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    # The star+json media type nests the repo; plain JSON does not. Accept both.
    return [row.get("repo", row) for row in data]


def clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render(repos: list[dict]) -> str:
    if not repos:
        return "```\n  NO STARRED REPOSITORIES RETURNED BY THE LAST SWEEP.\n```"

    lines = ["```", "┌" + "─" * WIDTH + "┐"]
    for repo in repos:
        name = clip(repo.get("full_name", "?"), 38)
        lang = clip(repo.get("language") or "—", 12)
        stars = f"★ {repo.get('stargazers_count', 0):,}"
        head = f"│ ▓ {name}"
        tail = f"{lang}  {stars} │"
        lines.append(head + " " * max(1, WIDTH + 2 - len(head) - len(tail)) + tail)

        desc = clip(repo.get("description") or "no description", WIDTH - 6)
        body = f"│   {desc}"
        lines.append(body + " " * max(1, WIDTH + 1 - len(body)) + "│")
        lines.append("├" + "─" * WIDTH + "┤")
    lines[-1] = "└" + "─" * WIDTH + "┘"
    lines.append("```")
    return "\n".join(lines)


def main() -> int:
    try:
        repos = fetch_starred()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as err:
        # A failed sweep must not rewrite the README with an error, and must not
        # fail the job either: the profile is still correct, just not refreshed.
        print(f"could not reach the GitHub API, leaving the README alone: {err}", file=sys.stderr)
        return 0

    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print("markers missing from README.md; nothing written", file=sys.stderr)
        return 1

    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    updated = f"{before}{START}\n{render(repos)}\n{END}{after}"

    if updated == text:
        print("no change")
        return 0

    README.write_text(updated, encoding="utf-8")
    print(f"rendered {len(repos)} starred repositories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
