#!/usr/bin/env python3
"""Automates the TOIL of adding assets, not the JUDGMENT of which to add.

Full auto-selection (guessing from filenames) was already tried once on this
project and got it wrong twice — see asset_manifest.yaml's header and
SETUP.md "Asset tagging". This tool instead:

  1. `generate` — scans ../AI video editor/Asset/ for files not yet decided
     on (tracked in asset_review_state.yaml), builds thumbnails, and writes
     an HTML gallery where you fill in role/formats per file you want and
     leave the rest. The page assembles your choices into a YAML block you
     copy out — no server, no clipboard permissions needed.
  2. `apply <decisions.yaml>` — takes what you copied out, does the
     mechanical work: copies approved files into public_assets/, appends
     asset_manifest.yaml entries, records every decision (including
     rejections, so a skipped file is never asked about again).

Usage:
    python3 review_new_assets.py generate
    python3 review_new_assets.py apply drafts/asset_review/decisions.yaml
"""
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
ASSET_SOURCE_DIR = PIPELINE_ROOT.parent / "AI video editor" / "Asset"
MANIFEST_PATH = PIPELINE_ROOT / "asset_manifest.yaml"
STATE_PATH = PIPELINE_ROOT / "asset_review_state.yaml"
PUBLIC_ASSETS_DIR = PIPELINE_ROOT / "public_assets"
GALLERY_DIR = PIPELINE_ROOT / "drafts" / "asset_review"
THUMBS_DIR = GALLERY_DIR / "thumbs"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
VIDEO_EXTS = {".mp4", ".mov", ".MP4", ".MOV"}
FFMPEG = shutil.which("ffmpeg") or str(Path.home() / "bin" / "ffmpeg")


def load_manifest():
    """Read-only — never write back a loaded-then-redumped manifest. Both YAML
    files here carry hand-written comments explaining why this process is
    manual at all; yaml.safe_dump on a safe_load'd dict silently drops every
    comment. All writes below splice new text in instead."""
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)


def load_state():
    if not STATE_PATH.exists():
        return {"reviewed": {}}
    with open(STATE_PATH) as f:
        return yaml.safe_load(f) or {"reviewed": {}}


def append_manifest_entries(new_entries):
    """Splices new asset blocks in as text, right before the `excluded:`
    section's lead comment — same spot a human editing this file by hand
    would add one. Leaves every existing byte, including comments, untouched."""
    text = MANIFEST_PATH.read_text()
    marker = "# Explicitly excluded,"
    idx = text.index(marker)
    blocks = ""
    for e in new_entries:
        formats_str = ", ".join(e["formats"])
        role = e["role"].replace('"', '\\"')
        caption = e["default_caption"].replace('"', '\\"')
        blocks += (
            f'  - id: {e["id"]}\n'
            f'    role: "{role}"\n'
            f'    type: {e["type"]}\n'
            f'    path: "{e["path"]}"\n'
            f'    formats: [{formats_str}]\n'
            f'    default_caption: "{caption}"\n\n'
        )
    MANIFEST_PATH.write_text(text[:idx] + blocks + text[idx:])


def append_state_entries(filename_to_status):
    """Splices new `filename: status` lines right after the `reviewed:` key,
    same comment-preserving approach as append_manifest_entries."""
    text = STATE_PATH.read_text()
    marker = "reviewed:\n"
    idx = text.index(marker) + len(marker)
    lines = "".join(f"  {fn}: {status}\n" for fn, status in filename_to_status.items())
    STATE_PATH.write_text(text[:idx] + lines + text[idx:])


def find_undecided():
    state = load_state()
    known = set(state.get("reviewed", {}).keys())
    all_files = [
        p for p in ASSET_SOURCE_DIR.rglob("*")
        if p.is_file() and not p.name.startswith(".") and (p.suffix in IMAGE_EXTS or p.suffix in VIDEO_EXTS)
    ]
    return [p for p in all_files if p.name not in known]


def make_thumbnail(src, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix in VIDEO_EXTS:
        cmd = [FFMPEG, "-y", "-ss", "1", "-i", str(src), "-frames:v", "1", "-vf", "scale=320:-1", str(out_path)]
    else:
        cmd = [FFMPEG, "-y", "-i", str(src), "-vf", "scale=320:-1", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)


def generate():
    undecided = find_undecided()
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    if not undecided:
        print("No undecided files — everything in Asset/ has already been reviewed.")
        return

    cards = []
    for f in sorted(undecided, key=lambda p: p.name):
        thumb_name = f"{f.stem}_{abs(hash(str(f))) % 10**8}.jpg"
        thumb_path = THUMBS_DIR / thumb_name
        try:
            make_thumbnail(f, thumb_path)
            thumb_src = f"thumbs/{thumb_name}"
        except subprocess.CalledProcessError:
            thumb_src = ""
        kind = "video" if f.suffix in VIDEO_EXTS else "image"
        cards.append(f"""
        <div class="card" data-filename="{f.name}">
          <div class="thumb">{f'<img src="{thumb_src}">' if thumb_src else '<div class="no-thumb">no preview</div>'}</div>
          <div class="filename">{f.name} <span class="kind">({kind})</span></div>
          <label><input type="checkbox" class="include"> Include</label>
          <label>Role: <input type="text" class="role" placeholder="e.g. Sunset Terrace"></label>
          <label>Formats:
            <select class="formats" multiple size="2">
              <option value="luxury_carousel" selected>luxury_carousel</option>
              <option value="cinematic_reel" selected>cinematic_reel</option>
            </select>
          </label>
          <label>Caption (optional): <input type="text" class="caption" placeholder="default_caption"></label>
        </div>""")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Asset review — {len(undecided)} undecided</title>
<style>
  body {{ background:#FAF8F5; color:#1F2E26; font-family: -apple-system, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.4em; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .card {{ border: 1px solid #EBE7E0; border-radius: 8px; padding: 12px; background: #EBE7E0; width: 260px; }}
  .thumb img {{ max-width: 100%; border-radius: 4px; }}
  .no-thumb {{ width: 100%; height: 140px; display:flex; align-items:center; justify-content:center;
               background:#ddd; border-radius:4px; font-size:0.8em; color:#666; }}
  .filename {{ font-size: 0.8em; margin: 6px 0; word-break: break-all; }}
  .kind {{ opacity: 0.6; }}
  label {{ display: block; font-size: 0.85em; margin-top: 6px; }}
  input[type=text] {{ width: 100%; box-sizing: border-box; }}
  button {{ background: #9F5E09; color: white; border: none; padding: 10px 16px;
            border-radius: 6px; font-size: 1em; cursor: pointer; margin: 16px 0; }}
  textarea {{ width: 100%; height: 240px; font-family: monospace; font-size: 0.85em; }}
</style></head>
<body>
  <h1>{len(undecided)} undecided file(s) in Asset/</h1>
  <p>Check "Include" + fill in a role for anything worth posting. Leave the rest unchecked —
     unchecked files are recorded as rejected once you apply, so they won't show up again.</p>
  <div class="grid">{"".join(cards)}</div>
  <button onclick="generateYaml()">Generate decisions YAML</button>
  <p>Copy the block below into a file (e.g. <code>drafts/asset_review/decisions.yaml</code>),
     then run <code>python3 scripts/review_new_assets.py apply drafts/asset_review/decisions.yaml</code></p>
  <textarea id="output" readonly placeholder="Click the button above..."></textarea>
<script>
function generateYaml() {{
  const cards = document.querySelectorAll('.card');
  let out = 'decisions:\\n';
  cards.forEach(card => {{
    const filename = card.dataset.filename;
    const include = card.querySelector('.include').checked;
    if (include) {{
      const role = card.querySelector('.role').value.trim() || '(FILL IN ROLE)';
      const caption = card.querySelector('.caption').value.trim();
      const formats = Array.from(card.querySelector('.formats').selectedOptions).map(o => o.value);
      out += `  - filename: "${{filename}}"\\n`;
      out += `    include: true\\n`;
      out += `    role: "${{role}}"\\n`;
      out += `    formats: [${{formats.join(', ')}}]\\n`;
      out += `    default_caption: "${{caption}}"\\n`;
    }} else {{
      out += `  - filename: "${{filename}}"\\n`;
      out += `    include: false\\n`;
    }}
  }});
  document.getElementById('output').value = out;
}}
</script>
</body></html>"""

    gallery_path = GALLERY_DIR / "gallery.html"
    gallery_path.write_text(html)
    print(f"Wrote {gallery_path} ({len(undecided)} undecided files)")
    print(f"Open it in a browser, fill in the files you want, click 'Generate decisions YAML',")
    print(f"save the copied text as {GALLERY_DIR / 'decisions.yaml'}, then run:")
    print(f"  python3 {Path(__file__).name} apply {GALLERY_DIR / 'decisions.yaml'}")


def apply(decisions_path):
    with open(decisions_path) as f:
        decisions = yaml.safe_load(f)["decisions"]

    manifest = load_manifest()
    next_id = max((a["id"] for a in manifest["assets"]), default=0) + 1

    new_entries, status_updates = [], {}
    added, rejected = [], []
    for d in decisions:
        filename = d["filename"]
        if not d.get("include"):
            status_updates[filename] = "rejected"
            rejected.append(filename)
            continue

        matches = list(ASSET_SOURCE_DIR.rglob(filename))
        if not matches:
            print(f"WARNING: {filename!r} not found under {ASSET_SOURCE_DIR}, skipping")
            continue

        dest = PUBLIC_ASSETS_DIR / filename
        dest.write_bytes(matches[0].read_bytes())

        entry = dict(
            id=next_id,
            role=d["role"],
            type="video" if Path(filename).suffix.lower() in {".mp4", ".mov"} else "image",
            path=f"public_assets/{filename}",
            formats=d.get("formats") or ["luxury_carousel", "cinematic_reel"],
            default_caption=d.get("default_caption", ""),
        )
        new_entries.append(entry)
        status_updates[filename] = "approved"
        added.append((next_id, d["role"], filename))
        next_id += 1

    if new_entries:
        append_manifest_entries(new_entries)
    if status_updates:
        append_state_entries(status_updates)

    print(f"Added {len(added)} asset(s):")
    for i, role, fn in added:
        print(f"  id {i}: {role} ({fn})")
    print(f"Rejected {len(rejected)} file(s) — won't be asked about again.")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("generate", "apply"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "generate":
        generate()
    else:
        if len(sys.argv) < 3:
            print("usage: review_new_assets.py apply <decisions.yaml>")
            sys.exit(1)
        apply(Path(sys.argv[2]))
