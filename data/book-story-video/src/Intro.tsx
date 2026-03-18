import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";

// ─── Masked text reveal (text rises up from below clip boundary) ──────────────
const MaskedReveal: React.FC<{
  startFrame: number;
  durationFrames?: number;
  children: React.ReactNode;
  height: number;
}> = ({ startFrame, durationFrames = 22, height, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.exp),
    }
  );

  const translateY = interpolate(progress, [0, 1], [height, 0]);

  return (
    <div style={{ overflow: "hidden", height, display: "flex", alignItems: "flex-end" }}>
      <div style={{ transform: `translateY(${translateY}px)` }}>{children}</div>
    </div>
  );
};

// ─── Horizontal rule that draws out from center ───────────────────────────────
const HRule: React.FC<{ startFrame: number; width: number; color?: string }> = ({
  startFrame,
  width,
  color = "rgba(255,255,255,0.22)",
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(frame, [startFrame, startFrame + 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });

  const opacity = interpolate(
    frame,
    [startFrame, startFrame + 8],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        width,
        height: 1,
        position: "relative",
        opacity,
        overflow: "hidden",
      }}
    >
      {/* draws from center outward using a pseudo clip */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: `${50 - progress * 50}%`,
          right: `${50 - progress * 50}%`,
          height: "100%",
          background: color,
        }}
      />
    </div>
  );
};

// ─── Small spaced-out label ───────────────────────────────────────────────────
const Label: React.FC<{
  startFrame: number;
  children: React.ReactNode;
  color?: string;
}> = ({ startFrame, children, color = "rgba(255,255,255,0.38)" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [startFrame, startFrame + fps * 0.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const translateY = interpolate(
    frame,
    [startFrame, startFrame + fps * 0.45],
    [10, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.quad),
    }
  );

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translateY}px)`,
        fontSize: 26,
        letterSpacing: 7,
        fontWeight: 300,
        color,
        fontFamily:
          "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
        textTransform: "uppercase",
      }}
    >
      {children}
    </div>
  );
};

// ─── Subtle ambient glow that pulses slowly ───────────────────────────────────
const AmbientGlow: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [0, fps * 0.5, fps * 3], [0, 0.65, 0.55], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // very slow horizontal drift
  const x = interpolate(frame, [0, fps * 3], [0, 3], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse 70% 45% at ${50 + x}% 48%, rgba(90,130,200,0.12) 0%, transparent 70%)`,
        opacity,
      }}
    />
  );
};

// ─── Vertical accent bar on the left ─────────────────────────────────────────
const AccentBar: React.FC<{ startFrame: number }> = ({ startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scaleY = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 200 },
    durationInFrames: fps * 0.6,
  });

  const opacity = interpolate(frame, [startFrame, startFrame + 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: 3,
        height: 132,
        background: "linear-gradient(to bottom, rgba(160,200,255,0.9), rgba(120,170,240,0.3))",
        borderRadius: 2,
        opacity,
        transformOrigin: "top center",
        transform: `scaleY(${scaleY})`,
      }}
    />
  );
};

// ─── Main composition ─────────────────────────────────────────────────────────
export const BookIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Bg fade in
  const bgOpacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Subtle scale-in on entire scene (creates cinematic "breathe in")
  const sceneScale = interpolate(frame, [0, fps * 3], [1.03, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Timing constants
  const TOP_LINE = 3;
  const BAR_START = 5;
  const TITLE_1 = 8;    // "书籍"
  const TITLE_2 = 17;   // "背后的故事"
  const BOT_LINE = 30;
  const LABEL_BOT = 37;

  return (
    <AbsoluteFill
      style={{
        // Deep midnight navy — NOT pure black
        background: "linear-gradient(160deg, #0e1626 0%, #111d30 45%, #0c1422 100%)",
        opacity: bgOpacity,
        transform: `scale(${sceneScale})`,
      }}
    >
      {/* Ambient blue glow */}
      <AmbientGlow />

      {/* Very subtle noise-like vignette around edges */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse 90% 90% at center, transparent 55%, rgba(6,10,20,0.8) 100%)",
        }}
      />

      {/* ── Central content column ── */}
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "flex-start",
            gap: 28,
          }}
        >
          {/* Left accent bar */}
          <div style={{ paddingTop: 10 }}>
            <AccentBar startFrame={BAR_START} />
          </div>

          {/* Title block */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
              gap: 0,
            }}
          >
            {/* Top rule */}
            <HRule startFrame={TOP_LINE} width={480} />

            <div style={{ height: 22 }} />

            {/* Line 1: 书籍 */}
            <MaskedReveal startFrame={TITLE_1} height={132}>
              <div
                style={{
                  fontSize: 125,
                  fontWeight: 300,
                  color: "#f5f2ec",
                  letterSpacing: 12,
                  lineHeight: 1,
                  fontFamily:
                    "'PingFang SC', 'Hiragino Mincho Pro', 'SimSun', serif",
                }}
              >
                书  籍
              </div>
            </MaskedReveal>

            {/* Line 2: 背后的故事 */}
            <MaskedReveal startFrame={TITLE_2} height={84} durationFrames={20}>
              <div
                style={{
                  fontSize: 70,
                  fontWeight: 200,
                  color: "rgba(245,242,236,0.82)",
                  letterSpacing: 16,
                  lineHeight: 1,
                  fontFamily:
                    "'PingFang SC', 'Hiragino Mincho Pro', 'SimSun', serif",
                }}
              >
                背后的故事
              </div>
            </MaskedReveal>

            <div style={{ height: 28 }} />

            {/* Bottom rule */}
            <HRule startFrame={BOT_LINE} width={480} />

            <div style={{ height: 20 }} />

            {/* Bottom label */}
            <Label startFrame={LABEL_BOT}>每 天 一 本</Label>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
