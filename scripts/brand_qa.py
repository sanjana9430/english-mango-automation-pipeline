"""Automated QA gate that stands in for the human approval step.

Passing this is what lets the pipeline publish with no human in the loop.
Anything it can't confidently verify should fail closed (QAResult.passed = False),
not pass by default — a missed check here is a wrong post on a real account.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED_CLAIM_WORDS = [
    "guaranteed", "cheapest", "#1", "best in india", "100% safe", "risk-free",
]

MAX_CAPTION_LEN = 2200  # Instagram's hard limit
MAX_HOOK_WORDS = 12
MAX_ON_SCREEN_LINES = 2

# reel_render_engine.py's generate_music_bed() is an explicitly-flagged
# placeholder (synthesized sine-wave pad, zero licensing risk, "swap for a
# real licensed track before this ships"). Fail every reel closed until
# that's actually true — set ALLOW_PLACEHOLDER_MUSIC=true only as a conscious,
# temporary call, not a default.
ALLOW_PLACEHOLDER_MUSIC = os.environ.get("ALLOW_PLACEHOLDER_MUSIC", "false").lower() == "true"


@dataclass
class QAResult:
    passed: bool
    reasons: list = field(default_factory=list)

    def fail(self, reason):
        self.passed = False
        self.reasons.append(reason)


def check(format_key, format_spec, selected_assets, draft):
    result = QAResult(passed=True)

    # Structural checks
    if "hook" not in draft or "caption" not in draft or "beats" not in draft:
        result.fail("draft is missing required fields (hook/caption/beats)")
        return result  # nothing else is safe to check against a malformed draft

    if len(draft["hook"].split()) > MAX_HOOK_WORDS:
        result.fail(f"hook exceeds {MAX_HOOK_WORDS} words")

    if len(draft["caption"]) > MAX_CAPTION_LEN:
        result.fail(f"caption exceeds Instagram's {MAX_CAPTION_LEN}-char limit")

    publish_type = format_spec["publish_type"]
    beat_count = len(draft["beats"])
    if publish_type == "carousel":
        if not (format_spec["min_slides"] <= beat_count <= format_spec["max_slides"]):
            result.fail(
                f"carousel has {beat_count} slides, expected "
                f"{format_spec['min_slides']}-{format_spec['max_slides']}"
            )
    elif publish_type == "reel":
        if not (format_spec["min_beats"] <= beat_count <= format_spec["max_beats"]):
            result.fail(
                f"reel has {beat_count} beats, expected "
                f"{format_spec['min_beats']}-{format_spec['max_beats']}"
            )
        if not ALLOW_PLACEHOLDER_MUSIC:
            result.fail(
                "reel render still uses reel_render_engine.py's synthesized placeholder "
                "music bed - swap for a licensed track, or set ALLOW_PLACEHOLDER_MUSIC=true "
                "once that's a deliberate, reviewed call"
            )

    # Every beat's asset_role must resolve to a real, selected asset
    valid_roles = {a["role"] for a in selected_assets}
    for beat in draft["beats"]:
        if beat.get("asset_role") not in valid_roles:
            result.fail(f"beat references unknown asset role: {beat.get('asset_role')!r}")
        lines = [l for l in beat.get("on_screen_text", "").split("\n") if l.strip()]
        if len(lines) > MAX_ON_SCREEN_LINES:
            result.fail(f"beat on-screen text exceeds {MAX_ON_SCREEN_LINES} lines: {beat.get('asset_role')!r}")

    # Claims / compliance check
    caption_lower = draft["caption"].lower()
    hook_lower = draft["hook"].lower()
    for phrase in BANNED_CLAIM_WORDS:
        if phrase in caption_lower or phrase in hook_lower:
            result.fail(f"unsubstantiated claim detected: {phrase!r}")

    return result


def write_review_queue(date, format_key, draft, selected_assets, qa_result, storyboard_path=None):
    path = ROOT / "review_queue" / f"{date.isoformat()}.json"
    path.write_text(json.dumps({
        "date": date.isoformat(),
        "format": format_key,
        "draft": draft,
        "selected_assets": selected_assets,
        "qa_reasons": qa_result.reasons,
        "storyboard_preview": str(storyboard_path) if storyboard_path else None,
    }, indent=2))
    return path
