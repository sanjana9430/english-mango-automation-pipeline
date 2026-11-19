"""Publishes a day's already-rendered, QA-passed content after a human has
reviewed it (see pending_publish/YYYY-MM-DD.json and orchestrate.py's
printed draft/video) and approved it. Publishes exactly what was already
rendered - never re-runs ideation or rendering, so the approved post always
matches what was reviewed, never a freshly-regenerated draft.

Not meant to be invoked directly with a real target_date outside
orchestrate.py's APPROVE_PUBLISH_DATE dispatch (see its __main__ block) -
that's what wires this to the production credentials/environment.
"""
import json
from pathlib import Path

import content_calendar
import git_sync
import publish_instagram

ROOT = Path(__file__).resolve().parents[1]
PENDING_DIR = ROOT / "pending_publish"


def main(target_date):
    path = PENDING_DIR / f"{target_date.isoformat()}.json"
    if not path.exists():
        print(f"{target_date}: no pending_publish entry found, nothing to approve.")
        return 1

    data = json.loads(path.read_text())
    if data["status"] != "awaiting_approval":
        print(f"{target_date}: status is {data['status']!r}, not awaiting_approval - refusing to re-publish.")
        return 1

    format_spec = content_calendar.format_spec(data["format"])
    draft = data["draft"]
    if format_spec["publish_type"] == "carousel":
        response = publish_instagram.publish_carousel(draft, data["selected_assets"])
    elif format_spec["publish_type"] == "reel":
        response = publish_instagram.publish_reel(draft, data["video_url"])
    else:
        raise ValueError(f"unknown publish_type: {format_spec['publish_type']!r}")

    publish_instagram.log_published(target_date, data["format"], response)
    data["status"] = "published"
    path.write_text(json.dumps(data, indent=2))
    git_sync.push_file(path.relative_to(ROOT), f"approved publish: {target_date} ({data['format']})")

    print(f"{target_date}: published after approval. {response}")
    return 0
