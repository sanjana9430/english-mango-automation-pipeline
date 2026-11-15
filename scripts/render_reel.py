"""Renders today's reel via remotion_render_engine.py (Remotion — real
animated transitions/typography, replacing the old pure-ffmpeg compositing
as of 2026-11-16, see /Users/sanjana/.claude/plans/snoopy-singing-squirrel.md)
and publishes the result to the same Render static site that hosts the
curated images, at a stable filename (reel-latest.mp4) so the public URL
never changes.

Rollback: reel_render_engine.py (the ffmpeg engine) is kept untouched. If
Remotion misbehaves in production, change the import below back to it — both
modules expose the same load_brand()/RAW_DIR/build_from_draft() contract.

Requires GITHUB_PUSH_TOKEN (see SETUP.md "Reel video hosting") — a fine-grained
PAT scoped to just this repo with Contents: write, used to push the updated
video file. (GITHUB_PUSH_TOKEN itself is needed on every run regardless of
format now, for asset-rotation state — see assets.py / git_sync.py — but only
reel days need it for the video specifically.)
"""
import os
import time
from pathlib import Path

import requests

import git_sync
import remotion_render_engine as reel_render_engine

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
STATIC_SITE_FILENAME = "reel-latest.mp4"


def build(target_date, draft, selected_assets):
    """Renders the reel for `target_date`, returns the local .mp4 path (under
    this repo's drafts/, same as every other per-day artifact)."""
    brand = reel_render_engine.load_brand()
    output_path = reel_render_engine.RAW_DIR / f"reel-{target_date.isoformat()}.mp4"
    return reel_render_engine.build_from_draft(draft, selected_assets, brand, output_path)


def publish_to_static_site(video_path, timeout_s=180):
    """Copies video_path to public_assets/reel-latest.mp4, commits + pushes,
    waits for the Render static site to actually serve the new bytes, and
    returns the stable public URL. Raises on push failure or if the deploy
    doesn't show up within timeout_s — callers should treat that as a QA-queue
    reason, not publish a stale or half-updated file."""
    dest = PIPELINE_ROOT / "public_assets" / STATIC_SITE_FILENAME
    dest.write_bytes(Path(video_path).read_bytes())
    new_size = dest.stat().st_size

    git_sync.push_file(dest.relative_to(PIPELINE_ROOT), f"reel: update {STATIC_SITE_FILENAME}")

    base = os.environ["PUBLIC_ASSET_BASE_URL"].rstrip("/")
    url = f"{base}/{STATIC_SITE_FILENAME}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.head(url, timeout=10)
        if resp.status_code == 200 and int(resp.headers.get("content-length", -1)) == new_size:
            return url
        time.sleep(5)
    raise TimeoutError(f"{url} did not reflect the new {new_size}-byte file within {timeout_s}s")
