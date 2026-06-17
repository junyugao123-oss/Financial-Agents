import { Composition, Folder } from "remotion";
import { JunyuQuantPromo } from "./JunyuQuantPromo";

const FPS = 30;
const DURATION_IN_FRAMES = 60 * FPS;

export const RemotionRoot = () => {
  return (
    <Folder name="Junyu-Promo">
      <Composition
        id="JunyuQuantPromoLandscape"
        component={JunyuQuantPromo}
        durationInFrames={DURATION_IN_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{ format: "landscape" as const }}
      />
      <Composition
        id="JunyuQuantPromoPortrait"
        component={JunyuQuantPromo}
        durationInFrames={DURATION_IN_FRAMES}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={{ format: "portrait" as const }}
      />
    </Folder>
  );
};
