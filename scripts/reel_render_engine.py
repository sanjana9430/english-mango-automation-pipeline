"""Self-contained reel-rendering engine for the automated daily pipeline.

Counterpart to ../../AI video editor/scripts/build_rough_cut.py, which stays
the hand-editing tool for manual drafts (reads the full Asset/ library, keeps
its own hand-curated ASSET_MANIFEST). This module renders whatever today's
Claude-generated draft + asset_manifest.yaml selection says, reading only from
this repo's own public_assets/ and references/ — so a Render deploy (which
only clones this repo, never the sibling AI video editor/ folder) has
everything it needs. If build_rough_cut.py's visual treatment (fonts, drawtext
styling, pacing, filter graphs) changes, mirror the change here too.

2026-11-16 pass: fixed inaudible music (loudnorm instead of a blind low
multiplier), added a permanent bottom-gradient scrim so on-screen text always
has contrast regardless of what's actually in the shot, anchored text from
the bottom of its block instead of a fixed top-y (so 2- vs 3-line captions
don't crowd or float inconsistently), added crossfade transitions between
beats (was a hard concat cut), and always append a fixed CTA/logo end card -
previously no beat ever did this, since Claude's generated beats only ever
reference real assets.
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
GRADIENT_PATH = REF_DIR / "gradient_scrim.png"
FFMPEG = shutil.which("ffmpeg") or str(Path.home() / "bin" / "ffmpeg")

TEXT_LINE_HEIGHT = 70  # fontsize 58 + line_spacing 12, kept in sync with render_beat below
TEXT_BOTTOM_MARGIN = 200
XFADE_DURATION = 0.4


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


def _text_top_y(canvas_height, caption_text):
    """Anchors the BOTTOM of the text block at a fixed distance from the
    frame's bottom edge, growing upward for longer captions - so a 3-line
    caption doesn't start higher/lower inconsistently relative to a 2-line
    one, and nothing crowds the very edge of the frame."""
    num_lines = max(len([l for l in wrap_caption(caption_text).split("\n") if l.strip()]), 1)
    return canvas_height - TEXT_BOTTOM_MARGIN - num_lines * TEXT_LINE_HEIGHT


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
        text_y = _text_top_y(h, beat["caption"])

        base_vf = (
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase:flags=lanczos,crop={pre_w}:{pre_h},"
            f"zoompan=z='min(zoom+0.0008,1.08)':d={frames}:s={w}x{h}:fps={fps}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
            f"unsharp=5:5:0.5:5:5:0.0"
        )
        filter_complex = f"[0:v]{base_vf}[base];[base][1:v]overlay=0:0[scrimmed]"
        final_label = "scrimmed"
        if has_caption:
            filter_complex += (
                f";[scrimmed]drawtext=fontfile='{font}':textfile='{caption_file}':fontcolor={fg}:"
                f"fontsize=58:line_spacing=12:shadowcolor={shadow}@0.85:shadowx=2:shadowy=2:"
                f"x=80:y={text_y}:text_align=left[out]"
            )
            final_label = "out"
        cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(src), "-loop", "1", "-i", str(GRADIENT_PATH),
               "-filter_complex", filter_complex, "-map", f"[{final_label}]", "-t", str(dur),
               "-r", str(fps), "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "16", str(out_path)]

    else:  # video
        src = ASSET_DIR / beat["assets"][0]
        fg = brand["caption_style"]["text_color"].replace("#", "0x")
        shadow = brand["caption_style"]["shadow_color"].replace("#", "0x")
        font = tmp / "Inter-SemiBold.ttf"
        text_y = _text_top_y(h, beat["caption"])

        base_vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
        filter_complex = f"[0:v]{base_vf}[base];[base][1:v]overlay=0:0[scrimmed]"
        final_label = "scrimmed"
        if has_caption:
            filter_complex += (
                f";[scrimmed]drawtext=fontfile='{font}':textfile='{caption_file}':fontcolor={fg}:"
                f"fontsize=58:line_spacing=12:shadowcolor={shadow}@0.85:shadowx=2:shadowy=2:"
                f"x=80:y={text_y}:text_align=left[out]"
            )
            final_label = "out"
        cmd = [FFMPEG, "-y", "-ss", "0", "-i", str(src), "-loop", "1", "-i", str(GRADIENT_PATH),
               "-filter_complex", filter_complex, "-map", f"[{final_label}]", "-an", "-t", str(dur),
               "-r", str(fps), "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "16", str(out_path)]

    subprocess.run(cmd, check=True, capture_output=True)


def generate_music_bed(duration, out_path):
    """Still a synthesized placeholder (zero licensing risk) - swap for a real
    licensed track before this ships for real. loudnorm targets -16 LUFS
    integrated so it's actually audible; the previous flat volume=0.35
    multiplier on an already-quiet synth measured -38dB mean, effectively
    silent on a phone speaker."""
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
        f"afade=t=in:d=2,afade=t=out:st={max(duration - 3, 0)}:d=3,"
        f"loudnorm=I=-16:LRA=11:TP=-1.5"
    )
    cmd = [FFMPEG, "-y", *inputs, "-filter_complex", filt, "-c:a", "aac", "-b:a", "160k", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)


def render(timeline, brand, output_path):
    beats_dir = RAW_DIR / "_beats"
    beats_dir.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="em_reel_"))
    for name in ["Inter-Regular.ttf", "Inter-SemiBold.ttf", "PlayfairDisplay-Regular.ttf", "PlayfairDisplay-SemiBold.ttf"]:
        shutil.copy(REF_DIR / "fonts" / name, tmp / name)

    beat_files, durations = [], []
    for beat in timeline["beats"]:
        out_path = beats_dir / f"beat_{beat['id']:02d}_{beat['role'].lower().replace(' ', '-').replace('/', '')}.mp4"
        render_beat(beat, brand, tmp, out_path)
        beat_files.append(out_path)
        durations.append(beat["duration"])

    fps = brand["canvas"]["fps"]
    silent_path = tmp / "concat_silent.mp4"

    if len(beat_files) == 1:
        shutil.copy(beat_files[0], silent_path)
        total_duration = durations[0]
    else:
        inputs = []
        for p in beat_files:
            inputs += ["-i", str(p)]
        filter_parts = []
        running_label, running_length = "0:v", durations[0]
        for i in range(1, len(beat_files)):
            offset = max(running_length - XFADE_DURATION, 0)
            out_label = f"v{i}"
            filter_parts.append(
                f"[{running_label}][{i}:v]xfade=transition=fade:duration={XFADE_DURATION}:offset={offset:.3f}[{out_label}]"
            )
            running_length = running_length + durations[i] - XFADE_DURATION
            running_label = out_label
        subprocess.run(
            [FFMPEG, "-y", *inputs, "-filter_complex", ";".join(filter_parts),
             "-map", f"[{running_label}]", "-r", str(fps), "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-preset", "slow", "-crf", "16", str(silent_path)],
            check=True, capture_output=True,
        )
        total_duration = running_length

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
    # Always present, never left to Claude to decide — a fixed brand element,
    # not a creative content choice. The manual build_rough_cut.py always had
    # one of these; the automated path never did until this fix.
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
