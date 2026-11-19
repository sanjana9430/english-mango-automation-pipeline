#!/usr/bin/env python3
"""Daily entrypoint. Run by Render's cron job (see ../render.yaml), not by hand
in a live Claude Code session.

    python orchestrate.py                     # today, real run
    python orchestrate.py --date 2026-11-18    # a specific date
    python orchestrate.py --dry-run            # full pipeline, skips the actual publish call
    python orchestrate.py --date ... --force-publish   # override a QA-failed day after you've checked it

2026-11-19: a QA-passed day no longer auto-publishes. It renders (reels) or
confirms assets are ready (carousels), writes the result to
pending_publish/YYYY-MM-DD.json, pushes that file so it survives this
container exiting, and prints the full draft + video/asset info to stdout
(the other durable surface - Render's logs) for a human to review. Nothing
reaches Instagram until that's approved - see publish_approved.py.
--force-publish still means what it always did: override a QA failure and
publish immediately without the review step, for a human who has already
looked at a failed day and decided to push it through anyway.
"""
import argparse
import json
import os
import sys
from datetime import date as date_cls
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv

load_dotenv()

import content_calendar
import assets as asset_lib
import ideate
import brand_qa
import storyboard
import publish_instagram
import publish_approved
import render_reel
import git_sync

ROOT = Path(__file__).resolve().parents[1]
PENDING_DIR = ROOT / "pending_publish"


def run(target_date, dry_run=False, force_publish=False):
    format_key = content_calendar.resolve_format(target_date)
    if format_key is None:
        print(f"{target_date}: nothing scheduled, skipping.")
        return 0

    format_spec = content_calendar.format_spec(format_key)
    selected = asset_lib.select_for_format(
        format_key,
        limit=format_spec.get("max_beats") or format_spec.get("max_slides"),
    )

    # Record usage (and push, so it survives to tomorrow's run) right after
    # selection, before QA — a QA-failed day still shouldn't keep re-picking
    # the same stale assets forever. Skipped entirely on --dry-run (including
    # the local write, not just the push) — "no side effects" should mean
    # exactly that.
    if not dry_run:
        asset_lib.mark_used(selected, target_date)
        git_sync.push_file(
            asset_lib.ROTATION_STATE_PATH.relative_to(asset_lib.ROOT),
            f"rotation: mark {len(selected)} asset(s) used for {target_date} ({format_key})",
        )

    draft = ideate.generate(format_key, format_spec, selected)
    ideate.save_draft(target_date, draft)

    storyboard_path = storyboard.build(target_date, format_key, format_spec, draft, selected)
    print(f"{target_date}: storyboard preview written to {storyboard_path}")

    qa_result = brand_qa.check(format_key, format_spec, selected, draft)

    if not qa_result.passed and not force_publish:
        queue_path = brand_qa.write_review_queue(
            target_date, format_key, draft, selected, qa_result, storyboard_path
        )
        print(f"{target_date}: QA failed, queued for review at {queue_path}")
        for reason in qa_result.reasons:
            print(f"  - {reason}")
        return 1  # non-zero so Render shows this run as failed/needs-attention

    if dry_run:
        print(f"{target_date}: dry run, QA passed, publish skipped.")
        return 0

    # Build what would actually be published once, regardless of
    # force_publish, so the forced-QA-failure-override path and the normal
    # held-for-review path always publish the exact same artifact.
    if format_spec["publish_type"] == "carousel":
        payload = {"selected_assets": selected}
    elif format_spec["publish_type"] == "reel":
        video_path = render_reel.build(target_date, draft, selected)
        payload = {"video_url": render_reel.publish_to_static_site(video_path)}
    else:
        raise ValueError(f"unknown publish_type: {format_spec['publish_type']!r}")

    if not force_publish:
        PENDING_DIR.mkdir(exist_ok=True)
        pending_path = PENDING_DIR / f"{target_date.isoformat()}.json"
        pending_path.write_text(json.dumps(dict(
            date=target_date.isoformat(), format=format_key, draft=draft,
            status="awaiting_approval", **payload,
        ), indent=2))
        git_sync.push_file(
            pending_path.relative_to(ROOT),
            f"pending publish: {target_date} ({format_key}), awaiting approval",
        )
        print(f"{target_date}: QA passed and rendered - awaiting publish approval.")
        print(f"  hook: {draft['hook']}")
        print(f"  caption:\n{draft['caption']}")
        if "video_url" in payload:
            print(f"  video: {payload['video_url']}")
        else:
            print(f"  assets: {[a['role'] for a in payload['selected_assets']]}")
        print(f"  To approve: set APPROVE_PUBLISH_DATE={target_date.isoformat()} and trigger a run.")
        return 0

    if format_spec["publish_type"] == "carousel":
        response = publish_instagram.publish_carousel(draft, payload["selected_assets"])
    else:
        response = publish_instagram.publish_reel(draft, payload["video_url"])

    publish_instagram.log_published(target_date, format_key, response)
    print(f"{target_date}: published. {response}")
    return 0


if __name__ == "__main__":
    # A separate mode, not a CLI flag: approving a pending publish must never
    # re-run ideation/rendering (it would regenerate different content than
    # what was actually reviewed), so it's dispatched before argparse rather
    # than threaded through run()'s normal path. Triggered by setting this
    # env var and firing an off-schedule run - see publish_approved.py.
    approve_date = os.environ.get("APPROVE_PUBLISH_DATE")
    if approve_date:
        sys.exit(publish_approved.main(date_cls.fromisoformat(approve_date)))

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=lambda s: date_cls.fromisoformat(s), default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-publish", action="store_true")
    args = parser.parse_args()

    target = args.date or date_cls.today()
    sys.exit(run(target, dry_run=args.dry_run, force_publish=args.force_publish))
