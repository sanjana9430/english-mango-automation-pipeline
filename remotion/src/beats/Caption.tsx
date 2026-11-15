import React from "react";
import { interpolate, staticFile, useCurrentFrame } from "remotion";
import type { Brand } from "../Root";

const TEXT_BOTTOM_MARGIN = 100; // px, safe-zone offset from the frame's bottom edge

export const Caption: React.FC<{ caption: string; brand: Brand }> = ({ caption, brand }) => {
  const frame = useCurrentFrame();
  if (!caption.trim()) return null;

  // Short fade/slide-up entrance over the beat's first ~10 frames — the one
  // thing drawtext in the old ffmpeg engine couldn't do at all.
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const translateY = interpolate(frame, [0, 10], [12, 0], { extrapolateRight: "clamp" });

  return (
    <>
      <img
        src={staticFile("assets/gradient_scrim.png")}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
      <div
        style={{
          position: "absolute",
          left: 80,
          right: 80,
          bottom: TEXT_BOTTOM_MARGIN,
          color: brand.caption_style.text_color,
          textShadow: `0 2px 10px ${brand.caption_style.shadow_color}`,
          fontFamily: "Inter, sans-serif",
          fontWeight: 600,
          fontSize: 58,
          lineHeight: 1.25,
          whiteSpace: "pre-wrap",
          opacity,
          transform: `translateY(${translateY}px)`,
        }}
      >
        {caption}
      </div>
    </>
  );
};
