"""Shared helper for committing + pushing a file back to this repo from
within a running pipeline job. Render cron containers don't keep local disk
between runs, so any state that needs to persist across days (the reel video,
asset-rotation state) has to round-trip through git instead.

2026-11-18: rewritten to use GitHub's REST Contents API instead of shelling
out to `git`. The first real production run crashed immediately with
"fatal: not a git repository" - Render's Docker build strips .git out of the
image (it isn't needed to run the app), so the running container was never a
real git checkout and local git commands never had a chance of working. The
REST API needs no local .git at all, so it works identically here and
locally - no more environment-dependent behavior.

Requires GITHUB_PUSH_TOKEN — a fine-grained PAT scoped to just this repo with
Contents: write. See SETUP.md.
"""
import base64
import os
from pathlib import Path

import requests

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "sanjana9430/english-mango-automation-pipeline"  # "owner/repo", not a URL
DEFAULT_BRANCH = "main"


def push_file(relative_path, commit_message):
    """relative_path is relative to PIPELINE_ROOT and must already be written
    to disk with its new contents before calling this."""
    token = os.environ["GITHUB_PUSH_TOKEN"]
    repo = os.environ.get("GITHUB_PUSH_REPO", DEFAULT_REPO)
    path_str = str(relative_path).replace(os.sep, "/")
    api_url = f"https://api.github.com/repos/{repo}/contents/{path_str}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    content_b64 = base64.b64encode((PIPELINE_ROOT / relative_path).read_bytes()).decode()

    existing = requests.get(api_url, headers=headers, params={"ref": DEFAULT_BRANCH}, timeout=30)
    sha = existing.json().get("sha") if existing.status_code == 200 else None

    payload = {"message": commit_message, "content": content_b64, "branch": DEFAULT_BRANCH}
    if sha:
        payload["sha"] = sha

    resp = requests.put(api_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()
