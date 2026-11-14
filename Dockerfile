FROM python:3.11-slim

# ffmpeg: reel_render_engine.py shells out to it for every beat.
# git: render_reel.py pushes the rendered video to this repo's own static site.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "scripts/orchestrate.py"]
