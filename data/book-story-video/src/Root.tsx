import { Composition } from "remotion";
import { BookStoryComposition } from "./Composition";
import { TOTAL_FRAMES } from "./content";

const FPS = 30;

export const RemotionRoot: React.FC = () => (
  <Composition
    id="BookStory"
    component={BookStoryComposition}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1080}
    height={1920}
    defaultProps={{}}
  />
);
