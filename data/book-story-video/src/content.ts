export type Scene = { id: string; image: string; narration: string; durationInFrames: number };
export type Sub = { text: string; startMs: number; endMs: number };

export const SCENES: Scene[] = [
  { id: "scene-01", image: "images/scene-01.jpg", narration: "", durationInFrames: 344 },
  { id: "scene-02", image: "images/scene-02.jpg", narration: "", durationInFrames: 344 },
  { id: "scene-03", image: "images/scene-03.jpg", narration: "", durationInFrames: 344 },
  { id: "scene-04", image: "images/scene-04.jpg", narration: "", durationInFrames: 344 }
];

export const SUBTITLES: Sub[] = [
  { text: "一天介绍一个书籍背后的故事", startMs: 0, endMs: 2211 },
  { text: "今天讲的是《飞鸟集》", startMs: 2211, endMs: 3911 },
  { text: "泰戈尔的《飞鸟集》在中国被禁过", startMs: 3911, endMs: 6462 },
  { text: "但凶手不是政府，是译者自己", startMs: 6462, endMs: 8673 },
  { text: "2015年12月", startMs: 8673, endMs: 10033 },
  { text: "作家冯唐的译本刚上架就炸锅了", startMs: 10033, endMs: 12414 },
  { text: "他把'The world puts ", startMs: 12414, endMs: 15475 },
  { text: "off its mask of va", startMs: 15475, endMs: 18536 },
  { text: "stness to its love", startMs: 18536, endMs: 21597 },
  { text: "r'译成了'大千世界在情人面前解开裤", startMs: 21597, endMs: 24658 },
  { text: "裆'，把萤火虫的相遇译成'舌吻'", startMs: 24658, endMs: 27379 },
  { text: "浙江文艺出版社顶了两个月压力", startMs: 27379, endMs: 29760 },
  { text: "最后自己主动召回，说怕青少年误读", startMs: 29760, endMs: 32481 },
  { text: "更讽刺的是，出版社特意澄清", startMs: 32481, endMs: 34692 },
  { text: "不是被举报，不是被施压", startMs: 34692, endMs: 36563 },
  { text: "是我们自己下架的", startMs: 36563, endMs: 37923 },
  { text: "一本诺贝尔奖诗集", startMs: 37923, endMs: 39283 },
  { text: "因为译者的'下半身风格'", startMs: 39283, endMs: 41324 },
  { text: "成了新中国罕见被出版社自我禁绝的翻译", startMs: 41324, endMs: 44385 },
  { text: "作品", startMs: 44385, endMs: 44725 },
  { text: "有时候，毁掉经典的不是敌人", startMs: 44725, endMs: 46936 },
  { text: "是太想标新立异的自己", startMs: 46936, endMs: 48636 }
];

export const TOTAL_FRAMES = 1480;
export const AUDIO_FILE = "audio.mp3";
export const BOOK_TITLE = "飞鸟集";
export const TITLE_CARD_MS = { startMs: 3466, endMs: 5966 };
export const INTRO_FRAMES = 104;
export const STORY_COVER = "story_cover.jpg";
