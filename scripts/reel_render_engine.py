"""Self-contained reel-rendering engine for the automated daily pipeline.

Counterpart to ../../AI video editor/scripts/build_rough_cut.py, which stays
the hand-editing tool for manual drafts (reads the full Asset/ library, keeps
its own hand-curated ASSET_MANIFEST). This module renders whatever today's
Claude-generated draft + asset_manifest.yaml selection says, reading only from
this repo's own public_assets/ and references/ — so a Render deploy (which
only clones this repo, never the sibling AI video editor/ folder) has
everything it needs. If build_rough_cut.py's visual treatment (fonts, drawtext
styling, pacing, filter graphs) changes, mirror the change here too.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "public_assets"
REF_DIR = ROOT / "references"
RAW_DIR = ROOT / "drafts"  # reuses the existing gitignored drafts/ dir for render intermediates
FFMPEG = shutil.which("ffmpeg") or str(Path.home() / "bin" / "ffmpeg")


def load_brand():
    with open(REF_DIR / "brand-tokens.json") as f:
        return json.load(f)


def ffmpeg_duration(path):
    out = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        return None
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def sequence(brand, manifest, timeline_path, project_name):
    pacing = brand["pacing"]
    beats = []
    for item in manifest:
        beat = dict(item)
        if item["type"] == "image":
            beat["duration"] = pacing["image_beat_seconds"]
        elif item["type"] == "video":
            src = ASSET_DIR / item["assets"][0]
            native = ffmpeg_duration(src) or pacing["video_beat_seconds"]
            beat["duration"] = min(pacing["video_beat_seconds"], native)
        else:
            beat["duration"] = 3.0
        beat["status"] = "pending"
        beat["note"] = ""
        beats.append(beat)

    timeline = dict(project=project_name, canvas=brand["canvas"], beats=beats, excluded=[])
    RAW_DIR.mkdir(exist_ok=True)
    with open(timeline_path, "w") as f:
        json.dump(timeline, f, indent=2)
    return timeline


def wrap_caption(text, max_chars=28):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def render_beat(beat, brand, tmp, out_path):
    canvas = brand["canvas"]
    w, h, fps = canvas["width"], canvas["height"], canvas["fps"]
    colors = brand["colors"]
    dur = beat["duration"]

    caption_file = tmp / f"caption_{beat['id']}.txt"
    caption_file.write_text(wrap_caption(beat["caption"]))
    has_caption = bool(beat["caption"].strip())

    if beat["type"] == "title":
        bg = colors["background"].replace("#", "0x")
        fg = colors["foreground"].replace("#", "0x")
        font = tmp / "PlayfairDisplay-SemiBold.ttf"
        vf = (
            f"drawtext=fontfile='{font}':textfile='{caption_file}':fontcolor={fg}:"
            f"fontsize=72:line_spacing=16:text_align=center:"
            f"x=(w-text_w)/2:y=(h-text_h)/2"
        )
        cmd = [FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c={bg}:s={w}x{h}:d={dur}:r={fps}",
               "-vf", vf, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "18", str(out_path)]

    elif beat["type"] == "image":
        src = ASSET_DIR / beat["assets"][0]
        frames = int(dur * fps)
        fg = brand["caption_style"]["text_color"].replace("#", "0x")
        shadow = brand["caption_style"]["shadow_color"].replace("#", "0x")
        font = tmp / "Inter-SemiBold.ttf"
        pre_w, pre_h = int(w * 1.5), int(h * 1.5)
        vf = (
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase:flags=lanczos,crop={pre_w}:{pre_h},"
            f"zoompan=z='min(zoom+0.0008,1.08)':d={frames}:s={w}x{h}:fps={fps}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
            f"unsharp=5:5:0.5:5:5:0.0"
        )
        if has_caption:
            vf += (
                f",drawtext=fontfile='{font}':textfile='{caption_file}':fontcolor={fg}:"
                f"fontsize=58:line_spacing=12:shadowcolor={shadow}@0.85:shadowx=2:shadowy=2:"
                f"x=80:y=h-380:text_align=left"
            )
        cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(src), "-t", str(dur),
               "-vf", vf, "-r", str(fps), "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "16", str(out_path)]

    else:  # video
        src = ASSET_DIR / beat["assets"][0]
        fg = brand["caption_style"]["text_color"].replace("#", "0x")
        shadow = brand["caption_style"]["shadow_color"].replace("#", "0x")
        font = tmp / "Inter-SemiBold.ttf"
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
        if has_caption:
            vf += (
                f",drawtext=fontfile='{font}':textfile='{caption_file}':fontcolor={fg}:"
                f"fontsize=58:line_spacing=12:shadowcolor={shadow}@0.85:shadowx=2:shadowy=2:"
                f"x=80:y=h-380:text_align=left"
            )
        cmd = [FFMPEG, "-y", "-ss", "0", "-i", str(src), "-t", str(dur),
               "-vf", vf, "-an", "-r", str(fps), "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "16", str(out_path)]

    subprocess.run(cmd, check=True, capture_output=True)


def generate_music_bed(duration, out_path):
    """Original ambient pad, synthesized from sine tones - zero licensing risk,
    a placeholder bed so the render isn't silent. STILL A PLACEHOLDER — swap
    for a real licensed track (Instagram's own audio library works fine)
    before this ships. See brand_qa.py's reel-specific check, which fails
    closed on every reel until that swap happens."""
    notes = [73.42, 110.0, 185.0, 220.0, 293.66]  # D2 A2 F#3 A3 D4 - warm open chord
    weights = [1.0, 0.8, 0.5, 0.4, 0.3]
    inputs = []
    for f in notes:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={duration}"]
    mix = "".join(f"[{i}]" for i in range(len(notes)))
    weight_str = " ".join(str(w) for w in weights)
    filt = (
        f"{mix}amix=inputs={len(notes)}:weights='{weight_str}':normalize=0,"
        f"highpass=f=50,lowpass=f=2500,tremolo=f=0.15:d=0.3,"
        f"aecho=0.6:0.5:500:0.3,"
        f"afade=t=in:d=2,afade=t=out:st={max(duration - 3, 0)}:d=3,volume=0.35"
    )
    cmd = [FFMPEG, "-y", *inputs, "-filter_complex", filt, "-c:a", "aac", "-b:a", "160k", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)


def render(timeline, brand, output_path):
    beats_dir = RAW_DIR / "_beats"
    beats_dir.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="em_reel_"))
    for name in ["Inter-Regular.ttf", "Inter-SemiBold.ttf", "PlayfairDisplay-Regular.ttf", "PlayfairDisplay-SemiBold.ttf"]:
        shutil.copy(REF_DIR / "fonts" / name, tmp / name)

    beat_files = []
    for beat in timeline["beats"]:
        out_path = beats_dir / f"beat_{beat['id']:02d}_{beat['role'].lower().replace(' ', '-').replace('/', '')}.mp4"
        render_beat(beat, brand, tmp, out_path)
        beat_files.append(out_path)

    list_path = tmp / "concat_list.txt"
    list_path.write_text("\n".join(f"file '{p}'" for p in beat_files))
    silent_path = tmp / "concat_silent.mp4"
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c", "copy", str(silent_path)], check=True, capture_output=True)

    total_duration = sum(b["duration"] for b in timeline["beats"])
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
    timeline_path = RAW_DIR / f"timeline-{output_path.stem}.json"
    timeline = sequence(brand, manifest, timeline_path, project_name=f"English Mango - {output_path.stem}")
    return render(timeline, brand, output_path)
