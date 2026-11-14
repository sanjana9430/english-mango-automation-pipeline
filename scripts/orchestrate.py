#!/usr/bin/env python3
"""Daily entrypoint. Run by Render's cron job (see ../render.yaml), not by hand
in a live Claude Code session.

    python orchestrate.py                     # today, real run
    python orchestrate.py --date 2026-11-18    # a specific date
    python orchestrate.py --dry-run            # full pipeline, skips the actual publish call
    python orchestrate.py --date ... --force-publish   # override a queued review after you've checked it
"""
import argparse
import sys
from datetime import date as date_cls
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv

load_dotenv()

import calendar as content_calendar  # local module, shadows stdlib `calendar` deliberately
import assets as asset_lib
import ideate
import brand_qa
import storyboard
import publish_instagram


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

    if format_spec["publish_type"] == "carousel":
        response = publish_instagram.publish_carousel(draft, selected)
    elif format_spec["publish_type"] == "reel":
        raise NotImplementedError(
            "Reel publishing needs a rendered final video (see ../AI video editor/scripts/"
            "build_rough_cut.py) plus a public video_url — wire that path in before relying "
            "on this for reel days."
        )
    else:
        raise ValueError(f"unknown publish_type: {format_spec['publish_type']!r}")

    publish_instagram.log_published(target_date, format_key, response)
    print(f"{target_date}: published. {response}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=lambda s: date_cls.fromisoformat(s), default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-publish", action="store_true")
    args = parser.parse_args()

    target = args.date or date_cls.today()
    sys.exit(run(target, dry_run=args.dry_run, force_publish=args.force_publish))
