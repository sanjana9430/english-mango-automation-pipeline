import React from "react";
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "./Caption";
import type { Beat, Brand } from "../Root";

// Zoom target matches the ffmpeg engine's old zoompan ceiling (z='min(zoom+0.0008,1.08)')
// — kept as a named constant here since brand-tokens.json's pacing.kenburns_zoom
// is a human-readable description, not a consumed numeric value.
const KEN_BURNS_ZOOM_TARGET = 1.08;

export const ImageBeat: React.FC<{ beat: Beat; brand: Brand }> = ({ beat, brand }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1.0, KEN_BURNS_ZOOM_TARGET], {
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: brand.colors.foreground }}>
      <img
        src={staticFile(`assets/${beat.assets[0]}`)}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
        }}
      />
      <Caption caption={beat.caption} brand={brand} />
    </div>
  );
};
