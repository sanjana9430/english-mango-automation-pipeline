# Setup — English Mango Instagram automation pipeline

This runs as a daily scheduled job (Render cron), **not** inside a live Claude Code
session — publishing to Instagram is an irreversible public action, so it has to be
your own deployed service with its own stored credentials.

Note: the Render static site was originally created by API with a plain repo
URL (no git repo existed yet at that point), which skips the GitHub App's
normal webhook installation — so auto-deploy-on-push silently didn't fire
until the Render GitHub App was given access to this repo under
https://github.com/settings/installations. Fixed 2026-11-15. If a future
push doesn't show up on Render within a minute or two, check that setting
first before assuming something else broke.

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

## 2. Asset tagging (per new asset, ~10 seconds of your time each)

`build_rough_cut.py` in `../AI video editor/scripts/` deliberately uses a
human-curated manifest instead of guessing from filenames — guessing already
produced two real mistakes on this project (a pre-landscaping "grass" shot used
as finished lawn; someone else's film mistaken for b-roll because it was
playing on a screen in frame). This pipeline reuses that same curated list
(`asset_manifest.yaml`) rather than re-guessing — this is the one place
"no human intervention" deliberately doesn't apply, because the cost of being
wrong (publishing a construction photo, or someone else's footage) is higher
than the cost of a quick look.

`scripts/review_new_assets.py` automates everything *except* that look. When
you drop new footage/photos into `../AI video editor/Asset/` (any subfolder):

```bash
python3 scripts/review_new_assets.py generate
```

This scans `Asset/` for anything not already decided on (tracked in
`asset_review_state.yaml`), builds thumbnails, and writes
`drafts/asset_review/gallery.html` — open it in a real browser (not a preview
pane; it needs local file access for the thumbnails). Check "Include" + fill
in a role for anything worth posting, leave the rest unchecked, click
"Generate decisions YAML", and save the text it produces as
`drafts/asset_review/decisions.yaml`. Then:

```bash
python3 scripts/review_new_assets.py apply drafts/asset_review/decisions.yaml
```

This copies approved files into `public_assets/`, appends their entries to
`asset_manifest.yaml`, and records every decision — including rejections, so
a file you skip is never shown again. Both YAML files get text spliced in,
not regenerated, so none of their hand-written comments get lost.

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

## 4. Asset rotation

Once eligible assets exceed a format's cap (`max_slides`/`max_beats` in
`content_calendar.yaml`), `assets.select_for_format()` doesn't just take the
first N in file order — it prefers whichever assets haven't been used
recently, so newly-approved assets actually enter rotation instead of being
silently starved out forever by file order. (This was a real bug, not a
hypothetical: the day `asset_review_state.yaml` added 4 new assets, all 4
would have been silently dropped from every reel under the old file-order
logic — caught and fixed the same day.)

That needs state (`asset_rotation_state.json`, tracking each asset's
last-used date) to persist across days — but Render cron containers don't
keep local disk between runs, so `orchestrate.py` pushes the updated file
back to git after every run (via `scripts/git_sync.py`), the same mechanism
section 5 below uses for the reel video. This is why `GITHUB_PUSH_TOKEN` is
needed on **every** run now, not just reel days.

## 5. Reel video rendering (Remotion) + hosting + the placeholder music bed

Cinematic Reel days render an actual video via **Remotion** (`remotion/`,
invoked by `scripts/remotion_render_engine.py` — as of 2026-11-16, replacing
the earlier pure-ffmpeg engine for genuinely better transitions/animated
typography; see the migration plan at
`~/.claude/plans/snoopy-singing-squirrel.md` for the full reasoning). The old
engine, `scripts/reel_render_engine.py`, is kept untouched as a one-line
rollback — if Remotion misbehaves in production, change `render_reel.py`'s
`import remotion_render_engine as reel_render_engine` back to plain
`import reel_render_engine`.

The rendered video needs its own public URL, same reasoning as step 3. Unlike
the curated images, the reel changes every time it runs — so rather than
growing the git history with a new file every reel day, `render_reel.py`
overwrites a single file, `public_assets/reel-latest.mp4`, commits, and
pushes that one change before publishing. The public URL
(`https://english-mango-assets.onrender.com/reel-latest.mp4`) never changes;
only its contents do.

`GITHUB_PUSH_TOKEN` (see section 4 — needed on every run, not just this one)
is a **fine-grained GitHub PAT**, scoped to only the
`english-mango-automation-pipeline` repo with **Contents: write** permission,
set in `.env` / the Render dashboard. Generate it at
https://github.com/settings/personal-access-tokens/new.

Separately: the music bed is still a synthesized placeholder (unchanged by
the Remotion migration — audio generation/muxing stayed in Python/ffmpeg on
purpose, see the migration plan's §3). `brand_qa.py` fails every reel closed
until you set `ALLOW_PLACEHOLDER_MUSIC=true` — a deliberate choice, not a
default. Do that once you've either accepted the placeholder for now, or
wired in a real track (Instagram's own in-app audio library is the easiest
licensed option).

## 6. Local Remotion testing

```bash
nvm install 22 && nvm use 22
cd automation-pipeline/remotion
npm install
```

Fast iteration on a beat component's look: `npx remotion studio --props=../drafts/_remotion_props/<file>.json`
(generate a real props file first by calling `remotion_render_engine._stage_assets()`
+ `_write_props()` directly, or just run the full pipeline once and reuse what
it wrote). Full-pipeline smoke test without touching git/QA/publish:
`python3 scripts/dev_verify_remotion.py drafts/<some-existing-draft>.json`.

**Known local-only issue, not a deployment problem**: on a Mac older than
macOS 15 (Sequoia), Remotion's downloaded Chrome Headless Shell *and* its
bundled ffmpeg binary both fail (`SIGABRT` / `EPIPE` respectively) — they're
built against newer OS APIs than an older Mac has. The deployed Linux Docker
container uses its own Linux builds of both and never hits this. Confirmed
locally on this project: pointing Chrome at a full, already-installed Chrome
browser via `REMOTION_BROWSER_EXECUTABLE=/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome`
fixes the Chrome-launch half (works fine for `remotion studio`, which never
touches the bundled-ffmpeg path) but doesn't fix the ffmpeg-encode half
(`renderMedia()` has no custom-ffmpeg-path option in Remotion v4) — so on an
old Mac, `remotion studio` is the real verification tool, and a full
server-side render has to wait for an actual deploy or a newer/Linux machine.

## 7. Deploy

```bash
cd automation-pipeline
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY, META_ACCESS_TOKEN, META_IG_USER_ID, GITHUB_PUSH_TOKEN
python scripts/orchestrate.py --dry-run   # runs the full pipeline, skips the actual publish
```

Note: `--dry-run` returns before the render step is ever reached (checked
before the carousel/reel branch in `orchestrate.py`'s `run()`) — it verifies
calendar/asset-selection/ideation/QA, not rendering. Use
`scripts/dev_verify_remotion.py` (section 6) to actually exercise a render.

Once that looks right, deploy `render.yaml` as a Render Blueprint. It defines
two services — deploy the static site (`english-mango-assets`) first, confirm
its `onrender.com` URL matches `PUBLIC_ASSET_BASE_URL` in the cron service's
config (update it if Render assigned a different subdomain), then deploy the
cron service with `ANTHROPIC_API_KEY`, `META_ACCESS_TOKEN`, `META_IG_USER_ID`,
and `GITHUB_PUSH_TOKEN` set as secrets in Render's dashboard —
**never commit `.env`**.

The cron service's `Dockerfile` changed with the Remotion migration: it now
builds from `node:22-bookworm-slim` (not `python:3.11-slim`) with Python
layered on top, installs Chrome Headless Shell's shared libraries, and runs
`npx remotion browser ensure` at build time to bake Chrome in. This adds real
build-time minutes over the old single `apt-get install ffmpeg git` — if
Render's build step has a timeout on whatever plan this service is on, check
that *before* the first real deploy, separately from the runtime-RAM
question below. Headless Chrome rendering is also meaningfully heavier than
pure ffmpeg was — unknown what Render plan tier this service needs; treat any
crash/OOM-kill in the cron logs after deploy as the signal to size up.

## What happens when something looks wrong

The QA gate (`scripts/brand_qa.py`) runs automatically before every publish. If it
fails or is low-confidence, the pipeline does **not** publish and does **not**
skip the day silently — it writes the full draft + storyboard + QA reasons to
`review_queue/YYYY-MM-DD.json` and exits non-zero (so Render's run shows as
failed, which you'll see). Fix and re-run with `--date YYYY-MM-DD` to retry that
day, or `--force-publish` to override the gate once you've reviewed it manually.
