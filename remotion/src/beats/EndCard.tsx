import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Beat, Brand } from "../Root";

// beat.caption arrives as "English Mango\nenglishmango.com" from
// build_from_draft()'s hardcoded CTA beat — split so the two lines can
// animate in with a slight stagger instead of appearing together.
export const EndCard: React.FC<{ beat: Beat; brand: Brand }> = ({ beat, brand }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [name, url] = beat.caption.split("\n");

  const nameSpring = spring({ frame, fps, config: { damping: 14 } });
  const nameOpacity = interpolate(nameSpring, [0, 1], [0, 1]);
  const nameScale = interpolate(nameSpring, [0, 1], [0.92, 1]);
  const urlOpacity = interpolate(frame, [10, 20], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 24,
        background: brand.colors.background,
      }}
    >
      <div
        style={{
          fontFamily: "Playfair Display, serif",
          fontWeight: 600,
          fontSize: 76,
          color: brand.colors.foreground,
          opacity: nameOpacity,
          transform: `scale(${nameScale})`,
        }}
      >
        {name}
      </div>
      {url ? (
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontWeight: 400,
            fontSize: 36,
            color: brand.colors.foreground,
            opacity: urlOpacity,
          }}
        >
          {url}
        </div>
      ) : null}
    </div>
  );
};
