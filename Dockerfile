FROM node:22-bookworm-slim

# Start from Node, not Python — Chrome Headless Shell's compatibility is the
# fragile dependency (specific shared libs, specific Chrome version Remotion
# itself expects), so build on the base Remotion's own docs target.
#
# ffmpeg: still needed — remotion_render_engine.py's music-bed synthesis and
#         final audio mux (Remotion's own bundled ffmpeg only handles its
#         own frame encoding, not this pipeline's separate audio step).
# git: render_reel.py / git_sync.py push rotation state + the reel video.
# python3/pip: pipeline orchestration (scripts/orchestrate.py).
# lib*: Chrome Headless Shell's runtime deps, per
#       https://www.remotion.dev/docs/docker — verify this list against the
#       installed Remotion version if a future bump breaks the build.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git python3 python3-pip \
    libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 \
    libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 \
    libpango-1.0-0 libcairo2 libcups2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Debian bookworm's system python3 is externally-managed (PEP 668) -
# --break-system-packages is fine here since this is a single-purpose
# container, not a shared dev machine.
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY remotion/package.json remotion/package-lock.json remotion/
RUN cd remotion && npm ci

# Bake a compatible Chrome Headless Shell into the image at build time so the
# deployed container is self-contained - no first-run download delay/failure
# mode on a cron container that gets no interactive retry.
RUN cd remotion && npx remotion browser ensure

COPY . .

CMD ["python3", "scripts/orchestrate.py"]
