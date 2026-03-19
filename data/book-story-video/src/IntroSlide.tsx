import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const IntroSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Fade in
  const fadeIn = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Chinese text springs in
  const chineseSpring = spring({
    frame: frame - 8,
    fps,
    config: { damping: 200 },
    durationInFrames: 25,
  });

  const chineseY = interpolate(chineseSpring, [0, 1], [40, 0]);

  // English text springs in with delay
  const englishSpring = spring({
    frame: frame - 18,
    fps,
    config: { damping: 200 },
    durationInFrames: 20,
  });

  const englishY = interpolate(englishSpring, [0, 1], [30, 0]);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "#0a0a0a",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 20,
        opacity: fadeIn,
      }}
    >
      {/* Decorative line */}
      <div
        style={{
          width: interpolate(chineseSpring, [0, 1], [0, 200]),
          height: 2,
          background: "linear-gradient(to right, transparent, #c8a96e, transparent)",
          marginBottom: 20,
        }}
      />

      {/* 今日分享的是 */}
      <div
        style={{
          fontSize: 88,
          fontWeight: 900,
          color: "#ffffff",
          textAlign: "center",
          fontFamily: "PingFang SC, Noto Sans SC, Source Han Sans, sans-serif",
          letterSpacing: 8,
          transform: `translateY(${chineseY}px)`,
          opacity: chineseSpring,
          textShadow: "0 0 40px rgba(200, 169, 110, 0.5)",
        }}
      >
        今日分享的是
      </div>

      {/* Sharing today is */}
      <div
        style={{
          fontSize: 44,
          fontWeight: 300,
          color: "#c8a96e",
          textAlign: "center",
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontStyle: "italic",
          letterSpacing: 3,
          transform: `translateY(${englishY}px)`,
          opacity: englishSpring,
        }}
      >
        Sharing today is
      </div>

      {/* Bottom decorative line */}
      <div
        style={{
          width: interpolate(englishSpring, [0, 1], [0, 200]),
          height: 2,
          background: "linear-gradient(to right, transparent, #c8a96e, transparent)",
          marginTop: 20,
        }}
      />
    </div>
  );
};
