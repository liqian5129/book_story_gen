import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AbsoluteFill, Sequence, staticFile, useCurrentFrame, useDelayRender, useVideoConfig,
} from "remotion";
import type { Caption } from "@remotion/captions";

const PLAYBACK_RATE = 1.0;
const PAGE_DURATION_MS = 2000;
const HIGHLIGHT_COLOR = "#FFD700";

type CaptionPage = { chars: Caption[]; startMs: number; endMs: number };

function groupIntoPages(captions: Caption[]): CaptionPage[] {
  const pages: CaptionPage[] = [];
  let group: Caption[] = [];
  let pageStartMs = 0;
  for (const cap of captions) {
    if (group.length === 0) pageStartMs = cap.startMs;
    if (cap.startMs - pageStartMs >= PAGE_DURATION_MS && group.length > 0) {
      pages.push({ chars: group, startMs: pageStartMs, endMs: group[group.length - 1].endMs });
      group = [cap];
      pageStartMs = cap.startMs;
    } else {
      group.push(cap);
    }
  }
  if (group.length > 0)
    pages.push({ chars: group, startMs: pageStartMs, endMs: group[group.length - 1].endMs });
  return pages;
}

const PageDisplay: React.FC<{ page: CaptionPage }> = ({ page }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const absoluteMs = page.startMs + (frame / fps) * 1000;
  return (
    <div style={{
      position: "absolute", bottom: 120, left: 0, right: 0,
      display: "flex", justifyContent: "center", padding: "0 40px",
    }}>
      <div style={{
        backgroundColor: "rgba(0,0,0,0.65)", borderRadius: 12,
        padding: "14px 24px", fontSize: 40, fontWeight: "bold",
        color: "white", textAlign: "center", lineHeight: 1.6,
        maxWidth: 980, wordBreak: "break-all",
      }}>
        {page.chars.map((cap) => (
          <span
            key={cap.startMs}
            style={{ color: cap.startMs <= absoluteMs && cap.endMs > absoluteMs ? HIGHLIGHT_COLOR : "white" }}
          >
            {cap.text}
          </span>
        ))}
      </div>
    </div>
  );
};

export const CaptionOverlay: React.FC<{ sceneId: string }> = ({ sceneId }) => {
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const { fps } = useVideoConfig();
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() => delayRender());
  const fetchCaptions = useCallback(async () => {
    try {
      const r = await fetch(staticFile(`captions/${sceneId}.json`));
      if (!r.ok) { continueRender(handle); return; }
      setCaptions(await r.json());
      continueRender(handle);
    } catch (e) { cancelRender(e); }
  }, [continueRender, cancelRender, handle, sceneId]);
  useEffect(() => { fetchCaptions(); }, [fetchCaptions]);
  const pages = useMemo(() => (captions ? groupIntoPages(captions) : []), [captions]);
  if (!captions) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {pages.map((page, index) => {
        const nextPage = pages[index + 1];
        const startFrame = Math.floor((page.startMs / 1000) * fps);
        const endFrame = nextPage
          ? Math.floor((nextPage.startMs / 1000) * fps)
          : Math.ceil((page.endMs / 1000) * fps) + Math.round(fps * 0.5);
        const durationInFrames = endFrame - startFrame;
        if (durationInFrames <= 0) return null;
        return (
          <Sequence key={index} from={startFrame} durationInFrames={durationInFrames} layout="none">
            <PageDisplay page={page} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
