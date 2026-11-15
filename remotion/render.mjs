import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Swallow EPIPE on stdout/stderr — some internal Remotion progress-reporting
// writes to stdout with carriage-return updates that can crash when stdout
// isn't a conventional terminal (seen locally in a sandboxed shell; harmless
// to ignore since it's purely a progress-display write, not the render itself).
process.stdout.on("error", (err) => { if (err.code !== "EPIPE") throw err; });
process.stderr.on("error", (err) => { if (err.code !== "EPIPE") throw err; });

function argAfter(flag) {
  const i = process.argv.indexOf(flag);
  if (i === -1 || i === process.argv.length - 1) {
    throw new Error(`missing required argument: ${flag}`);
  }
  return process.argv[i + 1];
}

async function main() {
  const propsPath = argAfter("--props");
  const outPath = argAfter("--out");
  const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf8"));

  // Local-dev-only override: this Mac's macOS version is too old for the
  // Chrome Headless Shell binary Remotion downloads by default (needs a
  // VideoToolbox symbol from macOS 15+). Deployed Docker container uses the
  // Linux build via the normal download path and never sets this env var.
  const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || undefined;

  const serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });
  const composition = await selectComposition({ serveUrl, id: "Reel", inputProps, browserExecutable });

  await renderMedia({
    serveUrl,
    composition,
    inputProps,
    codec: "h264",
    pixelFormat: "yuv420p",
    outputLocation: outPath,
    browserExecutable,
    // Caps peak RAM to a single Chrome process — correct trade for an
    // unattended daily cron job over render wall-clock speed.
    concurrency: 1,
    chromiumOptions: {
      // Render.com's managed Docker runtime doesn't expose --shm-size, so
      // the usual `docker run --shm-size=2g` fix for Chrome's /dev/shm
      // 64MB default isn't available to us. This flag makes Chrome write
      // shared memory to /tmp instead - slower, but avoids the crash
      // without needing platform-level support.
      flags: { "disable-dev-shm-usage": true },
    },
  });
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("remotion render failed:", err);
    process.exit(1);
  });
