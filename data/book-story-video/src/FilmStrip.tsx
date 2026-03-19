import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

// ── Layout constants ──────────────────────────────────────────────────────────
const FRAME_W = 480;
const FRAME_H = 860;
const FRAME_GAP = 48;
const FRAME_SPACING = FRAME_W + FRAME_GAP;
const STRIP_PAD_X = 140;        // blank leader / trailer on each end
const SPROCKET_ZONE = 90;       // height of perforation band (top + bottom)
const BORDER_H = 32;            // thick black bar top & bottom
const STRIP_H = BORDER_H * 2 + SPROCKET_ZONE * 2 + FRAME_H;

// Perforation hole size & rhythm
const PERF_W = 38;
const PERF_H = 24;
const PERF_INTERVAL = 68;

const books = [
  { image: "IMG_9915.JPG",                 title: "飘",                 author: "玛格丽特·米切尔" },
  { image: "IMG_9916.JPG",                 title: "杀死一只知更鸟",     author: "哈珀·李"         },
  { image: "IMG_9917.JPG",                 title: "人性的枷锁",         author: "毛姆"             },
  { image: "IMG_9919.JPG",                 title: "房思琪的初恋乐园",   author: "林奕含"           },
  { image: "IMG_9920.JPG",                 title: "局外人",             author: "加缪"             },
  { image: "IMG_9922.JPG",                 title: "生死疲劳",           author: "莫言"             },
  { image: "album_temp_1773829427.PNG",    title: "了不起的盖茨比",     author: "菲茨杰拉德"       },
  { image: "album_temp_1773829442.PNG",    title: "悉达多",             author: "赫尔曼·黑塞"     },
  { image: "album_temp_1773829578.PNG",    title: "老人与海",           author: "海明威"           },
];

const N = books.length;
// Total strip width: leader + all frames (last has no trailing gap) + trailer
const STRIP_W = STRIP_PAD_X * 2 + FRAME_SPACING * N - FRAME_GAP;

export const FILM_DURATION = 105; // 3.5 s @ 30 fps

// ── Perforation row ───────────────────────────────────────────────────────────
const Perforations: React.FC<{ bottom?: boolean }> = ({ bottom }) => {
  // Only render holes over the actual frame area, not in the leader/trailer padding
  const frameAreaW = STRIP_W - STRIP_PAD_X * 2;
  const count = Math.ceil(frameAreaW / PERF_INTERVAL) + 1;
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            [bottom ? "bottom" : "top"]: (SPROCKET_ZONE - PERF_H) / 2,
            left: STRIP_PAD_X + i * PERF_INTERVAL,
            width: PERF_W,
            height: PERF_H,
            backgroundColor: "#000",
            borderRadius: 3,
            boxShadow: "inset 0 0 0 1px #2a2010",
          }}
        />
      ))}
    </>
  );
};

// ── Main component ────────────────────────────────────────────────────────────
export const FilmStrip: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();

  // Sweep: strip enters from off-left, exits off-right
  const translateX = interpolate(
    frame,
    [0, durationInFrames],
    [-(STRIP_W - STRIP_PAD_X), width - STRIP_PAD_X - FRAME_W],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#080808",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {/* Background image — slow pan + brightness breathe */}
      <Img
        src={staticFile("sj-objio-XFWiZTa2Ub0-unsplash.jpg")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          filter: `blur(2px) sepia(15%) brightness(${interpolate(frame, [0, FILM_DURATION / 2, FILM_DURATION], [1.1, 1.2, 1.1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })})`,
          opacity: 0.65,
          transform: `scale(1.12) translateX(${interpolate(frame, [0, durationInFrames], [-2, 2], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%) translateY(${interpolate(frame, [0, durationInFrames], [1, -1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%)`,
        }}
      />
      {/* ── Film strip container ── */}
      <div
        style={{
          position: "absolute",
          width: STRIP_W,
          height: STRIP_H,
          top: (height - STRIP_H) / 2,
          left: 0,
          transform: `translateX(${translateX}px)`,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Top thick bar */}
        <div style={{
          height: BORDER_H,
          flexShrink: 0,
          backgroundColor: "#111008",
          borderBottom: "5px solid rgba(180,140,40,0.6)",
        }} />

        {/* Top perforations */}
        <div style={{ position: "relative", height: SPROCKET_ZONE, flexShrink: 0, backgroundColor: "#18140a" }}>
          <Perforations />
        </div>

        {/* Frame images */}
        <div
          style={{
            height: FRAME_H,
            flexShrink: 0,
            paddingLeft: STRIP_PAD_X,
            display: "flex",
            gap: FRAME_GAP,
            alignItems: "stretch",
            backgroundColor: "#18140a",
          }}
        >
          {books.map((book, i) => (
            <div
              key={i}
              style={{
                width: FRAME_W,
                height: FRAME_H,
                flexShrink: 0,
                position: "relative",
                overflow: "hidden",
                border: "3px solid #2e2510",
                outline: "1px solid #0a0804",
              }}
            >
              <Img
                src={staticFile(book.image)}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  filter: "sepia(18%) contrast(1.06) brightness(0.92)",
                }}
              />

              {/* Dark vignette + text gradient */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background:
                    "linear-gradient(to bottom, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.8) 100%)",
                }}
              />

              {/* Frame number (top-left, film-style) */}
              <div
                style={{
                  position: "absolute",
                  top: 8,
                  left: 10,
                  fontSize: 18,
                  fontFamily: "monospace",
                  color: "rgba(245,230,170,0.5)",
                  letterSpacing: 1,
                }}
              >
                {String(i + 1).padStart(2, "0")}
              </div>

              {/* Book title */}
              <div
                style={{
                  position: "absolute",
                  bottom: 14,
                  left: 0,
                  right: 0,
                  textAlign: "center",
                  color: "#f5e8bc",
                  fontSize: 22,
                  fontWeight: 700,
                  fontFamily: "PingFang SC, Noto Sans SC, sans-serif",
                  textShadow: "0 1px 6px rgba(0,0,0,0.95)",
                  letterSpacing: 1,
                  padding: "0 8px",
                }}
              >
                《{book.title}》
              </div>

              {/* Author */}
              <div
                style={{
                  position: "absolute",
                  bottom: -2,
                  left: 0,
                  right: 0,
                  textAlign: "center",
                  color: "rgba(220,200,140,0.8)",
                  fontSize: 16,
                  fontFamily: "PingFang SC, Noto Sans SC, sans-serif",
                  textShadow: "0 1px 4px rgba(0,0,0,0.95)",
                  letterSpacing: 1,
                }}
              >
                {book.author}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom perforations */}
        <div style={{ position: "relative", height: SPROCKET_ZONE, flexShrink: 0, backgroundColor: "#18140a" }}>
          <Perforations bottom />
        </div>

        {/* Bottom thick bar */}
        <div style={{
          height: BORDER_H,
          flexShrink: 0,
          backgroundColor: "#111008",
          borderTop: "5px solid rgba(180,140,40,0.6)",
        }} />
      </div>

      {/* Edge vignette to soften entrance/exit */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(to right, rgba(8,8,8,0.85) 0%, transparent 12%, transparent 88%, rgba(8,8,8,0.85) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
