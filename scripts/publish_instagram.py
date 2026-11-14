"""Publishes an approved draft to Instagram via the Meta Graph API.

Only ever called after brand_qa.check() has passed (or after an explicit
--force-publish review override) — never unconditionally. See SETUP.md.

Graph API requires each asset to be reachable at a public URL (it fetches
image_url/video_url itself, it won't take a local file). PUBLIC_ASSET_BASE_URL
must point at wherever selected assets are actually hosted (e.g. this pipeline's
own Render static site, or a bucket/CDN) — set it in .env once that's decided.
"""
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v19.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _asset_url(relative_path):
    """relative_path is like "public_assets/villa-lawn-green.jpg" (relative to
    the pipeline repo root). The static site's publish root IS public_assets/,
    so the public URL drops that prefix."""
    base = os.environ["PUBLIC_ASSET_BASE_URL"].rstrip("/")
    served_path = relative_path.split("public_assets/", 1)[-1]
    return f"{base}/{served_path.lstrip('/')}"


def _post(path, **params):
    params["access_token"] = os.environ["META_ACCESS_TOKEN"]
    resp = requests.post(f"{GRAPH_BASE}/{path}", data=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get(path, **params):
    params["access_token"] = os.environ["META_ACCESS_TOKEN"]
    resp = requests.get(f"{GRAPH_BASE}/{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _wait_for_container(container_id, timeout_s=300, poll_s=5):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _get(container_id, fields="status_code")["status_code"]
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"media container {container_id} failed processing")
        time.sleep(poll_s)
    raise TimeoutError(f"media container {container_id} did not finish in {timeout_s}s")


def publish_carousel(draft, selected_assets):
    ig_user_id = os.environ["META_IG_USER_ID"]
    by_role = {a["role"]: a for a in selected_assets}

    child_ids = []
    for beat in draft["beats"]:
        asset = by_role[beat["asset_role"]]
        container = _post(
            f"{ig_user_id}/media",
            image_url=_asset_url(asset["path"]),
            is_carousel_item=True,
        )
        child_ids.append(container["id"])

    carousel_container = _post(
        f"{ig_user_id}/media",
        media_type="CAROUSEL",
        caption=draft["caption"],
        children=",".join(child_ids),
    )
    _wait_for_container(carousel_container["id"])
    return _post(f"{ig_user_id}/media_publish", creation_id=carousel_container["id"])


def publish_reel(draft, video_url):
    """video_url is the already-public URL returned by
    render_reel.publish_to_static_site() — no relative-path join needed here,
    unlike publish_carousel's still-curated images."""
    ig_user_id = os.environ["META_IG_USER_ID"]
    container = _post(
        f"{ig_user_id}/media",
        media_type="REELS",
        video_url=video_url,
        caption=draft["caption"],
    )
    _wait_for_container(container["id"], timeout_s=900)
    return _post(f"{ig_user_id}/media_publish", creation_id=container["id"])


def log_published(date, format_key, response):
    path = ROOT / "published_log" / f"{date.isoformat()}.json"
    path.write_text(json.dumps({"date": date.isoformat(), "format": format_key, "response": response}, indent=2))
