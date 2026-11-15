import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import type { Beat, Brand } from "../Root";

export const TitleCard: React.FC<{ beat: Beat; brand: Brand }> = ({ beat, brand }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(frame, [0, 15], [0.96, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: brand.colors.background,
      }}
    >
      <div
        style={{
          fontFamily: "Playfair Display, serif",
          fontWeight: 600,
          fontSize: 72,
          lineHeight: 1.3,
          textAlign: "center",
          color: brand.colors.foreground,
          whiteSpace: "pre-wrap",
          opacity,
          transform: `scale(${scale})`,
        }}
      >
        {beat.caption}
      </div>
    </div>
  );
};
