"""Loads the hand-curated asset_manifest.yaml and selects assets for a format.

Deliberately no filename-based auto-matching — see SETUP.md "Asset tagging".
"""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "asset_manifest.yaml"


def load_manifest():
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)


def select_for_format(format_key, limit=None):
    manifest = load_manifest()
    eligible = [a for a in manifest["assets"] if format_key in a["formats"]]
    missing = [a for a in eligible if not (ROOT / a["path"]).resolve().exists()]
    if missing:
        raise FileNotFoundError(
            "asset_manifest.yaml references missing files: "
            + ", ".join(a["path"] for a in missing)
        )
    return eligible[:limit] if limit else eligible
