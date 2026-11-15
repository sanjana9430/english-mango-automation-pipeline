import React from "react";
import { useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { TitleCard } from "./beats/TitleCard";
import { ImageBeat } from "./beats/ImageBeat";
import { VideoBeat } from "./beats/VideoBeat";
import { EndCard } from "./beats/EndCard";
import type { Beat, ReelProps } from "./Root";

function renderBeat(beat: Beat, brand: ReelProps["brand"]) {
  if (beat.role === "CTA / End Card") return <EndCard beat={beat} brand={brand} />;
  if (beat.type === "title") return <TitleCard beat={beat} brand={brand} />;
  if (beat.type === "video") return <VideoBeat beat={beat} brand={brand} />;
  return <ImageBeat beat={beat} brand={brand} />;
}

export const Reel: React.FC<ReelProps> = ({ timeline, brand }) => {
  const { fps } = useVideoConfig();
  const xfadeFrames = Math.round(brand.xfade_duration * fps);

  return (
    <TransitionSeries>
      {timeline.beats.map((beat, i) => (
        <React.Fragment key={beat.id}>
          <TransitionSeries.Sequence durationInFrames={Math.round(beat.duration * fps)}>
            {renderBeat(beat, brand)}
          </TransitionSeries.Sequence>
          {i < timeline.beats.length - 1 ? (
            <TransitionSeries.Transition
              presentation={fade()}
              timing={linearTiming({ durationInFrames: xfadeFrames })}
            />
          ) : null}
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};
