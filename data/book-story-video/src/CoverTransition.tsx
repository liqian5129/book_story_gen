import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { INTRO_FRAMES, STORY_COVER } from "./content";

const PAUSE_FRAMES = 15; // 0.5s 静止展示胶片格（含呼吸浮动）
const ZOOM_FRAMES  = 28; // 0.93s 弹性放大到全屏

// 与 FilmStrip 保持一致的胶片格尺寸
const FILM_W = 480;
const FILM_H = 860;
const SCREEN_W = 1080;
const FINAL_SCALE = SCREEN_W / FILM_W; // ≈ 2.25

export const CoverTransition: React.FC = () => {
  const frame = useCurrentFrame();
  if (!STORY_COVER) return null;

  const showStart = INTRO_FRAMES - PAUSE_FRAMES - ZOOM_FRAMES;
  const zoomStart  = INTRO_FRAMES - ZOOM_FRAMES;
  if (frame < showStart) return null;

  // ── 整体渐显（遮住 FilmStrip）────────────────────────────────────────
  const fadeIn = interpolate(frame, [showStart, showStart + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // ── 暂停阶段：胶片格轻微上浮 + 呼吸缩放 ──────────────────────────────
  const pauseProgress = interpolate(
    frame,
    [showStart, zoomStart],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  // 上浮 0 → -7px，easeInOut sin 曲线
  const floatY = -7 * Math.sin(pauseProgress * Math.PI * 0.5);
  // 呼吸：1.0 → 1.012，让图片像在"呼吸"
  const breathe = 1 + 0.012 * Math.sin(pauseProgress * Math.PI);

  // ── 放大阶段进度（0→1，带 easeOut cubic） ────────────────────────────
  const zoomProgress = interpolate(
    frame,
    [zoomStart, INTRO_FRAMES],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic) }
  );

  // ── 弹簧叠加：单周期正弦钟形，制造轻微过冲再回落 ────────────────────
  const springOvershoot =
    0.05 * (FINAL_SCALE - 1) *
    Math.sin(zoomProgress * Math.PI) *
    Math.pow(1 - zoomProgress, 1.2);

  // ── 最终缩放值 ───────────────────────────────────────────────────────
  const rawScale = 1.0 + (FINAL_SCALE - 1.0) * zoomProgress;
  const zoomScale = frame < zoomStart
    ? breathe               // 暂停阶段：呼吸缩放
    : rawScale + springOvershoot; // 放大阶段：弹性缩放

  // ── 动态模糊：放大前段达到峰值后清晰（模拟对焦） ────────────────────
  const blurPx = frame < zoomStart
    ? 0
    : interpolate(
        zoomProgress,
        [0, 0.35, 1],
        [0, 2.0, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );

  // ── 亮度爆发：放大高潮时短暂提亮，模拟镜头进光 ────────────────────
  const brightness = frame < zoomStart
    ? 0.92
    : interpolate(
        zoomProgress,
        [0, 0.72, 0.88, 1],
        [0.92, 1.10, 1.02, 1.0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );

  // ── 胶片细节（边框 & 滤镜）随放大淡出 ─────────────────────────────
  const frameDetailOpacity = frame < zoomStart
    ? 1
    : interpolate(
        zoomProgress,
        [0, 0.55],
        [1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );

  // ── 光晕扫光：放大开始时一道对角斜光扫过 ──────────────────────────
  const sweepOpacity = frame < zoomStart
    ? 0
    : interpolate(
        zoomProgress,
        [0, 0.25, 0.55],
        [0, 0.18, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );

  // 放大时 transformOrigin 略微下移，产生向上揭开的电影感
  const originY = frame < zoomStart
    ? 50
    : interpolate(zoomProgress, [0, 1], [50, 54], {
        extrapolateLeft: "clamp", extrapolateRight: "clamp"
      });

  // 暂停阶段水平细微晃动（手持感）
  const jitterX = frame < zoomStart
    ? 0.4 * Math.sin(frame * 1.7) * (1 - pauseProgress * 0.5)
    : 0;

  return (
    <AbsoluteFill style={{ opacity: fadeIn }}>
      {/* 深色底层，盖住 FilmStrip */}
      <AbsoluteFill style={{ backgroundColor: "#080808" }} />

      {/* 居中的胶片格，执行缩放 */}
      <AbsoluteFill style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: FILM_W,
            height: FILM_H,
            position: "relative",
            overflow: "hidden",
            transform: `translate(${jitterX}px, ${floatY}px) scale(${zoomScale})`,
            transformOrigin: `center ${originY}%`,
          }}
        >
          {/* 书封图片：放大时色调还原 + 亮度爆发 + 模糊 */}
          <Img
            src={staticFile(STORY_COVER)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: [
                `sepia(${frameDetailOpacity * 18}%)`,
                `contrast(1.06)`,
                `brightness(${brightness})`,
                blurPx > 0 ? `blur(${blurPx.toFixed(2)}px)` : "",
              ].filter(Boolean).join(" "),
            }}
          />

          {/* 扫光：对角线光晕扫过 */}
          {sweepOpacity > 0 && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                opacity: sweepOpacity,
                background:
                  "linear-gradient(135deg, transparent 20%, rgba(255,240,200,0.9) 48%, rgba(255,240,200,0.7) 52%, transparent 80%)",
                pointerEvents: "none",
                mixBlendMode: "screen",
              }}
            />
          )}

          {/* 胶片边框（放大时淡出） */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: frameDetailOpacity,
              border: "3px solid #2e2510",
              outline: "1px solid #0a0804",
              boxSizing: "border-box",
              pointerEvents: "none",
            }}
          />

          {/* 顶底渐变（胶片氛围，放大时淡出） */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: frameDetailOpacity,
              background:
                "linear-gradient(to bottom, rgba(10,8,4,0.55) 0%, transparent 22%, transparent 76%, rgba(10,8,4,0.65) 100%)",
              pointerEvents: "none",
            }}
          />

          {/* 四角暗角（暂停阶段增强胶片质感） */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: frameDetailOpacity * 0.6,
              background:
                "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)",
              pointerEvents: "none",
            }}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
