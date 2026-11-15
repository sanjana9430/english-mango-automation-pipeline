"""Loads the hand-curated asset_manifest.yaml and selects assets for a format.

Deliberately no filename-based auto-matching — see SETUP.md "Asset tagging".

Once eligible assets exceed a format's cap, selection is least-recently-used:
never-used assets are preferred, so newly-approved ones actually enter
rotation instead of being silently dropped by file order forever (which is
exactly what happened the day this was added - see git history). The chosen
subset is returned in manifest order so narrative pacing (exterior -> gardens
-> pool -> ...) stays stable; only *which* assets make the cut rotates.
"""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "asset_manifest.yaml"
ROTATION_STATE_PATH = ROOT / "asset_rotation_state.json"


def load_manifest():
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)


def load_rotation_state():
    if not ROTATION_STATE_PATH.exists():
        return {}
    with open(ROTATION_STATE_PATH) as f:
        return json.load(f)


def save_rotation_state(state):
    with open(ROTATION_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def select_for_format(format_key, limit=None):
    manifest = load_manifest()
    eligible = [a for a in manifest["assets"] if format_key in a["formats"]]
    missing = [a for a in eligible if not (ROOT / a["path"]).resolve().exists()]
    if missing:
        raise FileNotFoundError(
            "asset_manifest.yaml references missing files: "
            + ", ".join(a["path"] for a in missing)
        )
    if not limit or len(eligible) <= limit:
        return eligible

    rotation = load_rotation_state()
    by_recency = sorted(eligible, key=lambda a: rotation.get(str(a["id"]), ""))
    chosen_ids = {a["id"] for a in by_recency[:limit]}
    return [a for a in eligible if a["id"] in chosen_ids]  # restore manifest order


def mark_used(selected_assets, date):
    """Call once per run, right after selection, regardless of whether the
    draft later passes QA — otherwise a QA-failed day would keep re-selecting
    the same stale assets forever. Caller is responsible for persisting the
    updated state file (git_sync.push_file) since Render cron containers
    don't keep local disk between runs."""
    rotation = load_rotation_state()
    for a in selected_assets:
        rotation[str(a["id"])] = date.isoformat()
    save_rotation_state(rotation)
