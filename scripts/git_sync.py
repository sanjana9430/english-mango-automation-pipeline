"""Shared helper for committing + pushing a file back to this repo from
within a running pipeline job. Render cron containers don't keep local disk
between runs, so any state that needs to persist across days (the reel video,
asset-rotation state) has to round-trip through git instead.

Requires GITHUB_PUSH_TOKEN — a fine-grained PAT scoped to just this repo with
Contents: write. See SETUP.md.
"""
import os
import subprocess
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "https://github.com/sanjana9430/english-mango-automation-pipeline"


def push_file(relative_path, commit_message):
    """relative_path is relative to PIPELINE_ROOT and must already be written
    to disk with its new contents before calling this."""
    token = os.environ["GITHUB_PUSH_TOKEN"]
    repo_url = os.environ.get("GITHUB_PUSH_REPO", DEFAULT_REPO)
    auth_url = repo_url.replace("https://", f"https://x-access-token:{token}@")

    subprocess.run(["git", "add", str(relative_path)], cwd=PIPELINE_ROOT, check=True)
    commit = subprocess.run(
        ["git", "-c", "user.name=english-mango-pipeline", "-c", "user.email=pipeline@englishmango.local",
         "commit", "-m", commit_message],
        cwd=PIPELINE_ROOT, capture_output=True, text=True,
    )
    if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
        raise RuntimeError(f"git commit failed: {commit.stdout}\n{commit.stderr}")
    subprocess.run(["git", "push", auth_url, "HEAD:main"], cwd=PIPELINE_ROOT, check=True)
