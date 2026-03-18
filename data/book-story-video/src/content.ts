export type Scene = { id: string; image: string; narration: string; durationInFrames: number };
export type Sub = { text: string; startMs: number; endMs: number };

export const SCENES: Scene[] = [
  { id: "scene-01", image: "images/scene-01.jpg", narration: "", durationInFrames: 177 },
  { id: "scene-02", image: "images/scene-02.jpg", narration: "", durationInFrames: 177 },
  { id: "scene-03", image: "images/scene-03.jpg", narration: "", durationInFrames: 176 },
  { id: "scene-04", image: "images/scene-04.jpg", narration: "", durationInFrames: 176 },
  { id: "scene-05", image: "images/scene-05.jpg", narration: "", durationInFrames: 176 },
  { id: "scene-06", image: "images/scene-06.jpg", narration: "", durationInFrames: 176 }
];

export const SUBTITLES: Sub[] = [
  { text: "一天介绍一个书籍背后的故事，", startMs: 0, endMs: 2771 },
  { text: "今天讲的是《西线无战事》。", startMs: 2771, endMs: 5344 },
  { text: "这本小说出版当天就卖疯了，", startMs: 5344, endMs: 7917 },
  { text: "五万册一扫而空，一年狂销五十万，", startMs: 7917, endMs: 11084 },
  { text: "可谁想到它越火，死得越快。", startMs: 11084, endMs: 13657 },
  { text: "1930年德国直接禁了它，", startMs: 13657, endMs: 16230 },
  { text: "奥地利不让士兵碰，", startMs: 16230, endMs: 18011 },
  { text: "捷克斯洛伐克的军事图书馆把它扫地出门", startMs: 18011, endMs: 21573 },
  { text: "。", startMs: 21573, endMs: 21770 },
  { text: "三年后希特勒上台，这本书被当众焚毁，", startMs: 21770, endMs: 25332 },
  { text: "浓烟里烧掉的不只是纸，", startMs: 25332, endMs: 27509 },
  { text: "是一个国家不敢面对的真相。", startMs: 27509, endMs: 30082 },
  { text: "作者雷马克被迫流亡，", startMs: 30082, endMs: 32061 },
  { text: "十几年后成了美国人。", startMs: 32061, endMs: 34040 },
  { text: "有时候，一本书的命运，", startMs: 34040, endMs: 36217 },
  { text: "就是一个时代的照妖镜。", startMs: 36217, endMs: 38394 }
];

export const TOTAL_FRAMES = 1172;
export const AUDIO_FILE = "audio.mp3";
export const BOOK_TITLE = "西线无战事";
export const TITLE_CARD_MS = { startMs: 3800, endMs: 6300 };
export const INTRO_FRAMES = 114;
