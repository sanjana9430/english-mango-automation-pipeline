"""Generates hook + caption + per-beat on-screen text for today's format,
grounded in the brand sheet, via the Claude API (not a live chat session)."""
import json
import os
from pathlib import Path

from anthropic import Anthropic

ROOT = Path(__file__).resolve().parents[1]
# A local copy, not a reach across to ../AI video editor/ — that sibling folder
# only exists on the working machine, never in the deployed Render container
# (only this repo gets cloned there). Re-sync if the source brand sheet changes.
BRAND_SHEET = ROOT / "references" / "brand-sheet.md"

SYSTEM_PROMPT = """You write Instagram copy for English Mango, a luxury villa stay \
in Haridwar. Follow the attached brand sheet exactly: tone, caption structure, \
on-screen text rules. Output strict JSON matching the given schema, nothing else."""

OUTPUT_SCHEMA = {
    "hook": "string, <= 12 words, the first line shown on-screen or as the opening caption line",
    "caption": "string, the full Instagram caption using the feature_list structure from the brand sheet",
    "beats": [
        {"asset_role": "string, must match one of the given asset roles", "on_screen_text": "string, <= 2 short lines"}
    ],
}


def generate(format_key, format_spec, selected_assets):
    brand_sheet_text = BRAND_SHEET.read_text()
    asset_roles = [a["role"] for a in selected_assets]

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        thinking={"type": "disabled"},  # extended thinking is on by default for this
                                        # model/account and was consuming the entire
                                        # token budget before any text came out —
                                        # not needed for straightforward copy generation
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"BRAND SHEET:\n{brand_sheet_text}\n\n"
                    f"FORMAT: {format_spec['label']} ({format_spec['publish_type']})\n"
                    f"AVAILABLE ASSET ROLES (use only these, in a sensible order): {asset_roles}\n\n"
                    f"Produce exactly {len(asset_roles)} beats total - one beat per asset role "
                    f"listed above, each role used exactly once, in the order given. Do not "
                    f"repeat a role or add extra beats, even if that count feels short.\n\n"
                    f"OUTPUT SCHEMA (strict JSON, no prose outside the JSON):\n{json.dumps(OUTPUT_SCHEMA, indent=2)}"
                ),
            }
        ],
    )
    text_blocks = [b.text for b in message.content if b.type == "text"]
    if not text_blocks:
        raise RuntimeError(f"no text block in Claude's response (got: {[b.type for b in message.content]})")
    text = text_blocks[0].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    # Claude sometimes adds a trailing sentence after the JSON object despite
    # the system prompt's "nothing else" - decode just the first JSON value
    # and ignore anything after it, rather than requiring the whole string to
    # be valid JSON (which broke a real run on 2026-11-18).
    obj, _ = json.JSONDecoder().raw_decode(text)
    return obj


def save_draft(date, draft):
    path = ROOT / "drafts" / f"{date.isoformat()}.json"
    path.write_text(json.dumps(draft, indent=2))
    return path
