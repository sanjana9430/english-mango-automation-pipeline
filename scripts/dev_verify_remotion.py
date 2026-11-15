#!/usr/bin/env python3
"""Smoke-test the Remotion render path against an existing saved draft,
touching none of orchestrate.py's git push, asset-rotation mutation, QA gate,
or publish logic. Exercises the exact function production calls
(remotion_render_engine.build_from_draft()) before trusting it in the real
cron job — see the migration-verification section of
/Users/sanjana/.claude/plans/snoopy-singing-squirrel.md.

Usage:
    python3 scripts/dev_verify_remotion.py drafts/2026-11-17.json
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv

load_dotenv()

import assets as asset_lib
import remotion_render_engine as engine


def main(draft_path):
    draft = json.loads(Path(draft_path).read_text())
    roles_needed = {b["asset_role"] for b in draft["beats"]}

    # Re-derive selected_assets from the manifest rather than re-running
    # asset selection - this is a replay of an already-made draft, not a new
    # day's run, so it shouldn't touch rotation state.
    manifest = asset_lib.load_manifest()
    selected = [a for a in manifest["assets"] if a["role"] in roles_needed]
    missing = roles_needed - {a["role"] for a in selected}
    if missing:
        print(f"WARNING: roles in draft no longer in asset_manifest.yaml: {missing}")

    brand = engine.load_brand()
    output_path = engine.RAW_DIR / f"dev-verify-{Path(draft_path).stem}.mp4"
    print(f"Rendering via remotion_render_engine.build_from_draft() -> {output_path}")
    engine.build_from_draft(draft, selected, brand, output_path)

    print("Render succeeded. Probing output...")
    subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                     "stream=width,height,codec_name,r_frame_rate:format=duration",
                     "-of", "default=noprint_wrappers=0", str(output_path)], check=False)
    print(f"\nOpen it to eyeball transitions/captions/Ken-Burns/end card:\n  open '{output_path}'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: dev_verify_remotion.py <path-to-draft.json>")
        sys.exit(1)
    main(sys.argv[1])
