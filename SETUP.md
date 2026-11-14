# Setup — English Mango Instagram automation pipeline

This runs as a daily scheduled job (Render cron), **not** inside a live Claude Code
session — publishing to Instagram is an irreversible public action, so it has to be
your own deployed service with its own stored credentials.

Three things only you can do (they all require logging into your own accounts):

## 1. Meta Developer App + Instagram access token

1. Go to https://developers.facebook.com/apps and create an app (type: "Business").
2. Add the **Instagram Graph API** product to the app.
3. Make sure the Instagram account you're posting to is a **Business or Creator**
   account, and that it's linked to a Facebook Page you manage.
4. In Graph API Explorer (or via the app's dashboard), generate a **Page access
   token** for that Page with these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
5. Exchange the short-lived token for a **long-lived token** (~60 days):
   ```
   GET https://graph.facebook.com/v19.0/oauth/access_token
       ?grant_type=fb_exchange_token
       &client_id={app-id}
       &client_secret={app-secret}
       &fb_exchange_token={short-lived-token}
   ```
3. Find your **Instagram Business Account ID**:
   ```
   GET https://graph.facebook.com/v19.0/{page-id}?fields=instagram_business_account&access_token={token}
   ```
6. Put the long-lived token and IG account ID into `.env` (copy `.env.example`).

Long-lived tokens expire. You'll need a refresh job eventually — flagging it now
so it doesn't surprise you in ~60 days; not building it until the rest is proven out.

## 2. Asset tagging (one-time, per asset)

`build_rough_cut.py` in `../AI video editor/scripts/` deliberately uses a
human-curated manifest instead of guessing from filenames — guessing already
produced two real mistakes on this project (a pre-landscaping "grass" shot used
as finished lawn; someone else's film mistaken for b-roll because it was
playing on a screen in frame). This pipeline reuses that same curated list
(`asset_manifest.yaml`) rather than re-guessing.

When you add new footage/photos to `../AI video editor/Asset/`, add one line to
`asset_manifest.yaml` yourself — same reasoning as the video editor's own
manifest. This is the one place "no human intervention" deliberately doesn't
apply, because the cost of being wrong (publishing a construction photo, or
someone else's footage) is higher than the cost of one line of YAML.

## 3. Asset hosting

Meta's Graph API fetches each image/video itself over a public URL — it can't
read a file off your laptop, and the cron job below runs on Render's servers,
not your Mac, so a local folder path never works here either way.

`public_assets/` in this repo holds a canonical copy of just the assets listed
in `asset_manifest.yaml` (not the full 171MB raw-footage folder — only the
already-approved ones). `render.yaml` deploys it as its own small Render
static site. When you approve a new asset in `../AI video editor/Asset/`, copy
it into `public_assets/` too and add the matching line to `asset_manifest.yaml`
— same one-line-per-asset discipline as step 2 above.

## 4. Reel video hosting + the placeholder music bed

Cinematic Reel days render an actual video (`scripts/reel_render_engine.py`,
the automated counterpart to `../AI video editor/scripts/build_rough_cut.py`)
and need their own public URL, same reasoning as step 3. Unlike the 8 fixed
curated images, the reel changes every time it runs — so rather than growing
the git history with a new ~20MB file every reel day, `render_reel.py`
overwrites a single file, `public_assets/reel-latest.mp4`, commits, and pushes
that one change before publishing. The public URL
(`https://english-mango-assets.onrender.com/reel-latest.mp4`) never changes;
only its contents do.

This needs a **fine-grained GitHub PAT**, scoped to only the
`english-mango-automation-pipeline` repo with **Contents: write** permission,
set as `GITHUB_PUSH_TOKEN` in `.env` / the Render dashboard. Generate it at
https://github.com/settings/personal-access-tokens/new.

Separately: `reel_render_engine.py`'s audio track is a synthesized placeholder
(the original `build_rough_cut.py`'s own docstring flagged this — "swap for a
real licensed track before this ships"). That's still true here. Rather than
silently ship synthetic audio on every reel, `brand_qa.py` fails every reel
closed until you set `ALLOW_PLACEHOLDER_MUSIC=true` — a deliberate choice, not
a default. Do that once you've either accepted the placeholder for now, or
wired in a real track (Instagram's own in-app audio library is the easiest
licensed option).

## 5. Deploy

```bash
cd automation-pipeline
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY, META_ACCESS_TOKEN, META_IG_USER_ID, GITHUB_PUSH_TOKEN
python scripts/orchestrate.py --dry-run   # runs the full pipeline, skips the actual publish
```

Once a few dry runs look right, deploy `render.yaml` as a Render Blueprint. It
defines two services — deploy the static site (`english-mango-assets`) first,
confirm its `onrender.com` URL matches `PUBLIC_ASSET_BASE_URL` in the cron
service's config (update it if Render assigned a different subdomain), then
deploy the cron service (it builds from `Dockerfile`, which installs `ffmpeg`
and `git` — the plain Render python runtime has neither) with
`ANTHROPIC_API_KEY`, `META_ACCESS_TOKEN`, `META_IG_USER_ID`, and
`GITHUB_PUSH_TOKEN` set as secrets in Render's dashboard —
**never commit `.env`**.

## What happens when something looks wrong

The QA gate (`scripts/brand_qa.py`) runs automatically before every publish. If it
fails or is low-confidence, the pipeline does **not** publish and does **not**
skip the day silently — it writes the full draft + storyboard + QA reasons to
`review_queue/YYYY-MM-DD.json` and exits non-zero (so Render's run shows as
failed, which you'll see). Fix and re-run with `--date YYYY-MM-DD` to retry that
day, or `--force-publish` to override the gate once you've reviewed it manually.
