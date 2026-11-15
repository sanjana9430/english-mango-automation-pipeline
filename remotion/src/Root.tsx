import React from "react";
import { Composition, staticFile } from "remotion";
import { loadFont as loadFontRaw } from "@remotion/fonts";
import { Reel } from "./Reel";

// Loaded once at module scope — Remotion's delayRender() (used internally by
// loadFont) blocks the first frame until these resolve, so no explicit
// Suspense/await wiring is needed here.
loadFontRaw({ family: "Inter", url: staticFile("fonts/Inter-Regular.ttf"), weight: "400" });
loadFontRaw({ family: "Inter", url: staticFile("fonts/Inter-SemiBold.ttf"), weight: "600" });
loadFontRaw({ family: "Playfair Display", url: staticFile("fonts/PlayfairDisplay-Regular.ttf"), weight: "400" });
loadFontRaw({ family: "Playfair Display", url: staticFile("fonts/PlayfairDisplay-SemiBold.ttf"), weight: "600" });

export type Beat = {
  id: number;
  role: string;
  type: "title" | "image" | "video";
  assets: string[];
  caption: string;
  duration: number; // seconds, already resolved by Python's sequence()
};

export type Timeline = {
  project: string;
  canvas: { width: number; height: number; fps: number };
  beats: Beat[];
};

export type Brand = {
  colors: Record<string, string>;
  caption_style: {
    text_color: string;
    shadow_color: string;
    max_lines: number;
  };
  xfade_duration: number; // seconds — added to brand-tokens.json's pacing; see SETUP.md
};

export type ReelProps = {
  timeline: Timeline;
  brand: Brand;
};

const FPS_FALLBACK = 30;

function totalDurationInFrames(timeline: Timeline, xfadeSeconds: number, fps: number) {
  const sumSeconds = timeline.beats.reduce((acc, b) => acc + b.duration, 0);
  const transitionSeconds = Math.max(timeline.beats.length - 1, 0) * xfadeSeconds;
  return Math.max(Math.round((sumSeconds - transitionSeconds) * fps), fps);
}

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Reel"
      component={Reel}
      // Placeholder defaults — calculateMetadata overrides all of these from
      // the real inputProps before any frame renders. Beat count/length
      // varies by day, so nothing here can be hardcoded.
      durationInFrames={FPS_FALLBACK * 10}
      fps={FPS_FALLBACK}
      width={1080}
      height={1920}
      defaultProps={{
        timeline: { project: "", canvas: { width: 1080, height: 1920, fps: 30 }, beats: [] },
        brand: { colors: {}, caption_style: { text_color: "#FAF8F5", shadow_color: "#1F2E26", max_lines: 2 }, xfade_duration: 0.4 },
      } as ReelProps}
      calculateMetadata={async ({ props }) => {
        const { timeline, brand } = props as ReelProps;
        const fps = timeline.canvas.fps;
        return {
          durationInFrames: totalDurationInFrames(timeline, brand.xfade_duration, fps),
          fps,
          width: timeline.canvas.width,
          height: timeline.canvas.height,
        };
      }}
    />
  );
};
