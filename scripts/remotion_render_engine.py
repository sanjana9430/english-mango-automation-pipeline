"""Remotion-based reel rendering engine — replaces reel_render_engine.py's
pure-ffmpeg compositing for the visual/transition/text layer (per the
2026-11-16 Remotion migration plan: /Users/sanjana/.claude/plans/
snoopy-singing-squirrel.md). Reuses reel_render_engine.py's pacing,
brand-loading, ffmpeg-duration-probing, and music-bed helpers directly rather
than duplicating them — those are unrelated to how frames get composited.

reel_render_engine.py is left untouched as the rollback path: flip
render_reel.py's import back to it if this misbehaves in production.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from reel_render_engine import ASSET_DIR, FFMPEG, REF_DIR, RAW_DIR, generate_music_bed, load_brand, sequence

ROOT = Path(__file__).resolve().parents[1]
REMOTION_DIR = ROOT / "remotion"
PROPS_DIR = RAW_DIR / "_remotion_props"

# Seconds. Must match the crossfade duration baked into remotion/src/Reel.tsx
# via brand.xfade_duration in the props this module writes - kept as one
# constant here rather than two independent magic numbers in Python and TS.
XFADE_DURATION = 0.4

# Longer edge, px. Curated source photos run up to 6000x4000 (two are
# 2528x1696) - full camera resolution, way past what a 1080x1920 output with
# modest Ken-Burns zoom needs. Chrome decodes each <Img> to an uncompressed
# bitmap, so staging originals straight through was ballooning the render's
# memory footprint (confirmed: the 2026-11-18 run OOM-killed at >2GB on a
# 9-beat reel whose assets included a 24-megapixel JPEG). 2160 gives ~2x the
# output height for zoom headroom with a fraction of the decoded memory.
IMAGE_MAX_EDGE = 2160


def _stage_assets(timeline):
    """Remotion's staticFile() only resolves against its own public/ dir -
    copy this run's handful of referenced files in before invoking Node."""
    assets_dir = REMOTION_DIR / "public" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for beat in timeline["beats"]:
        for fname in beat["assets"]:
            dest = assets_dir / fname
            if beat["type"] == "image":
                subprocess.run(
                    [FFMPEG, "-y", "-i", str(ASSET_DIR / fname), "-vf",
                     f"scale='min({IMAGE_MAX_EDGE},iw)':'min({IMAGE_MAX_EDGE},ih)':force_original_aspect_ratio=decrease",
                     "-update", "1", "-frames:v", "1", str(dest)],
                    check=True, capture_output=True,
                )
            else:
                shutil.copy(ASSET_DIR / fname, dest)
    shutil.copy(REF_DIR / "gradient_scrim.png", assets_dir / "gradient_scrim.png")

    fonts_dir = REMOTION_DIR / "public" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for name in ["Inter-Regular.ttf", "Inter-SemiBold.ttf", "PlayfairDisplay-Regular.ttf", "PlayfairDisplay-SemiBold.ttf"]:
        shutil.copy(REF_DIR / "fonts" / name, fonts_dir / name)


def _write_props(timeline, brand, stem):
    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    props = {
        "timeline": timeline,
        "brand": {
            "colors": brand["colors"],
            "caption_style": brand["caption_style"],
            "xfade_duration": XFADE_DURATION,
        },
    }
    props_path = PROPS_DIR / f"{stem}.json"
    props_path.write_text(json.dumps(props))
    return props_path


def render(timeline, brand, output_path):
    _stage_assets(timeline)
    props_path = _write_props(timeline, brand, output_path.stem)

    tmp = Path(tempfile.mkdtemp(prefix="em_remotion_"))
    silent_path = tmp / "silent.mp4"
    result = subprocess.run(
        ["node", "render.mjs", "--props", str(props_path), "--out", str(silent_path)],
        cwd=REMOTION_DIR, capture_output=True, text=True,
    )
    if result.returncode != 0:
        # check=True's CalledProcessError doesn't print stdout/stderr on its
        # own - without this, a Chrome/Node crash (SIGABRT, OOM) shows up in
        # cron logs as just a signal number with no indication of why.
        print(f"render.mjs failed (exit {result.returncode}):")
        print("--- stdout ---\n" + result.stdout)
        print("--- stderr ---\n" + result.stderr)
        result.check_returncode()

    total_duration = sum(b["duration"] for b in timeline["beats"]) - \
        max(len(timeline["beats"]) - 1, 0) * XFADE_DURATION
    music_path = tmp / "music_bed.m4a"
    generate_music_bed(total_duration, music_path)

    subprocess.run([FFMPEG, "-y", "-i", str(silent_path), "-i", str(music_path),
                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(output_path)],
                   check=True, capture_output=True)
    shutil.rmtree(tmp)
    return output_path


def build_from_draft(draft, selected_assets, brand, output_path):
    by_role = {a["role"]: a for a in selected_assets}
    manifest = []
    for i, beat in enumerate(draft["beats"], start=1):
        asset = by_role[beat["asset_role"]]
        manifest.append(dict(
            id=i,
            role=asset["role"],
            type=asset["type"],
            assets=[Path(asset["path"]).name],
            caption=beat.get("on_screen_text", ""),
        ))
    # Always present, never left to Claude to decide — see reel_render_engine.py's
    # identical comment on this same pattern.
    manifest.append(dict(
        id=len(manifest) + 1,
        role="CTA / End Card",
        type="title",
        assets=[],
        caption="English Mango\nenglishmango.com",
    ))
    timeline_path = RAW_DIR / f"timeline-{output_path.stem}.json"
    timeline = sequence(brand, manifest, timeline_path, project_name=f"English Mango - {output_path.stem}")
    return render(timeline, brand, output_path)
