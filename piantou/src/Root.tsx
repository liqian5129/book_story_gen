import React from "react";
import { Composition } from "remotion";
import { BookIntro } from "./Intro";

export const RemotionRoot = () => {
  return (
    <Composition
      id="BookIntro"
      component={BookIntro}
      durationInFrames={55}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
