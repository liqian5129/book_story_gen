import {
  AbsoluteFill, Audio, Easing, Img, Sequence, Series, interpolate, staticFile,
  useCurrentFrame, useVideoConfig,
} from "remotion";
import { SCENES, AUDIO_FILE, SUBTITLES, BOOK_TITLE, TITLE_CARD_MS, INTRO_FRAMES, STORY_COVER } from "./content";
import { FilmStrip } from "./FilmStrip";
import { CoverTransition } from "./CoverTransition";

// ── Ken Burns 镜头运动 ──────────────────────────────────────────
type KBMove = { fromScale: number; toScale: number; fromX: number; toX: number; fromY: number; toY: number };
const KB_MOVES: KBMove[] = [
  { fromScale: 1.00, toScale: 1.15, fromX:  0,   toX:  0,   fromY:  0,   toY:  0   },
  { fromScale: 1.15, toScale: 1.00, fromX:  0,   toX:  0,   fromY:  0,   toY:  0   },
  { fromScale: 1.08, toScale: 1.16, fromX: -2.5, toX:  2.5, fromY:  0,   toY:  0   },
  { fromScale: 1.08, toScale: 1.16, fromX:  2.5, toX: -2.5, fromY:  0,   toY:  0   },
  { fromScale: 1.10, toScale: 1.16, fromX:  0,   toX:  0,   fromY:  2.5, toY: -2.5 },
  { fromScale: 1.16, toScale: 1.08, fromX:  0,   toX:  0,   fromY: -2,   toY:  2   },
];
const FADE = 10;

const Scene: React.FC<{ image: string; duration: number; index: number }> = ({ image, duration, index }) => {
  const frame = useCurrentFrame();
  const kb = KB_MOVES[index % KB_MOVES.length];
  const t = interpolate(frame, [0, duration], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  const scale = kb.fromScale + (kb.toScale - kb.fromScale) * t;
  const tx    = kb.fromX    + (kb.toX    - kb.fromX)    * t;
  const ty    = kb.fromY    + (kb.toY    - kb.fromY)    * t;
  // 第一场景不淡入（与片头转场直接衔接），其余场景正常淡入淡出
  const opacity = index === 0
    ? interpolate(frame, [0, Math.max(1, duration - FADE), duration], [1, 1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : interpolate(frame, [0, FADE, Math.max(FADE + 1, duration - FADE), duration], [0, 1, 1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: "#000", opacity }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img src={staticFile(image)} style={{
          width: "100%", height: "100%", objectFit: "cover",
          transform: `scale(${scale}) translate(${tx}%, ${ty}%)`,
          transformOrigin: "center center",
          willChange: "transform",
        }} />
      </AbsoluteFill>
      <AbsoluteFill style={{
        background: "linear-gradient(to bottom, rgba(0,0,0,0.35) 0%, transparent 28%, transparent 58%, rgba(0,0,0,0.6) 100%)"
      }} />
    </AbsoluteFill>
  );
};

// ── 字幕：逐句切换 ─────────────────────────────────────────────
const SubtitleOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const sub = SUBTITLES.find(s => ms >= s.startMs && ms < s.endMs);
  if (!sub) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{
        position: "absolute", bottom: 320, left: 48, right: 48,
        backgroundColor: "rgba(0,0,0,0.3)",
        borderRadius: 14, padding: "18px 28px", textAlign: "center",
      }}>
        <span style={{
          color: "#fff", fontSize: 48, fontWeight: 600, lineHeight: 1.65,
          fontFamily: "'PingFang SC','Noto Sans CJK SC','Hiragino Sans GB',sans-serif",
          textShadow: "0 2px 8px rgba(0,0,0,0.8)",
        }}>{sub.text}</span>
      </div>
    </AbsoluteFill>
  );
};

// ── 书名卡：在"今天讲的是《xxx》"那句淡入显示，然后淡出 ──────────
const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const { startMs, endMs } = TITLE_CARD_MS;
  if (ms < startMs || ms >= endMs) return null;
  const FADE_MS = 350;
  const opacity = interpolate(
    ms,
    [startMs, startMs + FADE_MS, endMs - FADE_MS, endMs],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      <div style={{
        position: "absolute",
        top: 768,
        left: "50%",
        transform: "translateX(-50%)",
        backgroundColor: "rgba(0,0,0,0.72)",
        border: "2px solid rgba(255,255,255,0.25)",
        borderRadius: 20, padding: "40px 60px", textAlign: "center",
        whiteSpace: "nowrap",
      }}>
        <div style={{
          color: "rgba(255,220,100,0.9)", fontSize: 30, marginBottom: 16, letterSpacing: 4,
          fontFamily: "'PingFang SC','Noto Sans CJK SC',sans-serif",
        }}>今日好书</div>
        <div style={{
          color: "#fff", fontSize: 108, fontWeight: 700, lineHeight: 1.3,
          fontFamily: "'PingFang SC','Noto Sans CJK SC',sans-serif",
          textShadow: "0 4px 20px rgba(0,0,0,0.6)",
        }}>《{BOOK_TITLE}》</div>
      </div>
    </AbsoluteFill>
  );
};

// ── 主合成 ────────────────────────────────────────────────────
const AUDIO_DELAY_FRAMES = 18; // 0.6s 延迟开始

export const BookStoryComposition: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={AUDIO_DELAY_FRAMES}>
      <Audio src={staticFile(AUDIO_FILE)} />
    </Sequence>
    <Series>
      {INTRO_FRAMES > 0 && (
        <Series.Sequence durationInFrames={INTRO_FRAMES}>
          <FilmStrip />
          <CoverTransition />
          <Audio src={staticFile("reel.mp3")} volume={1.2} />
        </Series.Sequence>
      )}
      {SCENES.map((scene, i) => (
        <Series.Sequence key={scene.id} durationInFrames={scene.durationInFrames}>
          <Scene image={scene.image} duration={scene.durationInFrames} index={i} />
        </Series.Sequence>
      ))}
    </Series>
    <SubtitleOverlay />
    <TitleCard />
  </AbsoluteFill>
);
