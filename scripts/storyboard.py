"""Builds a storyboard preview (JSON + static HTML) for a draft.

Generated for every run, pass or fail, so there's always a visual record of
what would have gone out — this is the audit trail that replaces a human
clicking "approve" on a dashboard each time.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND_TOKENS = ROOT / "references" / "brand-tokens.json"  # local copy, see ideate.py's note


def _slide_html(beat, asset, tokens):
    colors = tokens["colors"]
    caption = beat.get("on_screen_text", "").replace("\n", "<br>")
    return f"""
    <div class="slide">
      <div class="asset-label">{asset['role']} &middot; {asset['path']}</div>
      <div class="caption" style="color:{colors['background']}; text-shadow:0 1px 6px {colors['foreground']};">
        {caption}
      </div>
    </div>
    """


def build(date, format_key, format_spec, draft, selected_assets):
    tokens = json.loads(BRAND_TOKENS.read_text())
    colors = tokens["colors"]
    by_role = {a["role"]: a for a in selected_assets}

    slides = []
    for beat in draft["beats"]:
        asset = by_role.get(beat.get("asset_role"))
        if asset:
            slides.append(_slide_html(beat, asset, tokens))

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{date} - {format_spec['label']}</title>
<style>
  body {{ background:{colors['background']}; color:{colors['foreground']};
         font-family: Inter, sans-serif; padding: 24px; }}
  h1 {{ font-family: "Playfair Display", serif; }}
  .hook {{ font-size: 1.4em; margin-bottom: 1em; }}
  .slide {{ border: 1px solid {colors['muted']}; border-radius: 8px; padding: 16px;
            margin-bottom: 12px; background: {colors['muted']}; }}
  .asset-label {{ font-size: 0.8em; opacity: 0.7; }}
  .caption {{ font-size: 1.1em; margin-top: 8px; }}
  .meta {{ font-size: 0.85em; opacity: 0.7; }}
</style></head>
<body>
  <h1>{format_spec['label']} &mdash; {date}</h1>
  <div class="hook">{draft.get('hook', '')}</div>
  {''.join(slides)}
  <h3>Caption</h3>
  <pre style="white-space: pre-wrap; font-family: Inter, sans-serif;">{draft.get('caption', '')}</pre>
  <p class="meta">Publish type: {format_spec['publish_type']}</p>
</body></html>"""

    storyboard = {
        "date": date.isoformat(),
        "format": format_key,
        "hook": draft.get("hook"),
        "caption": draft.get("caption"),
        "beats": draft["beats"],
    }

    json_path = ROOT / "drafts" / f"{date.isoformat()}-storyboard.json"
    html_path = ROOT / "drafts" / f"{date.isoformat()}-storyboard.html"
    json_path.write_text(json.dumps(storyboard, indent=2))
    html_path.write_text(html)
    return html_path
