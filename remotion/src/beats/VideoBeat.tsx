import React from "react";
import { OffthreadVideo, staticFile } from "remotion";
import { Caption } from "./Caption";
import type { Beat, Brand } from "../Root";

export const VideoBeat: React.FC<{ beat: Beat; brand: Brand }> = ({ beat, brand }) => {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: brand.colors.foreground }}>
      {/* muted: required for parity with the old engine's `-an` — Remotion
          audio here would conflict with the music bed muxed in afterward */}
      <OffthreadVideo
        src={staticFile(`assets/${beat.assets[0]}`)}
        muted
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
      <Caption caption={beat.caption} brand={brand} />
    </div>
  );
};
