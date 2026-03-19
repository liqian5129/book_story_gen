import sqlite3
import httpx
import json
import asyncio
import os
import math
import re
import uuid
import base64
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── 读取 .env 配置（不依赖第三方库）────────────────────────────────────────
def load_env(path=".env"):
    env = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

_env = load_env()

def cfg(key: str, default: str = "") -> str:
    return _env.get(key) or os.environ.get(key) or default

async def run_subprocess(cmd, **kwargs):
    """在线程池中运行阻塞式 subprocess，避免阻塞 asyncio 事件循环。"""
    loop = asyncio.get_event_loop()
    import functools
    return await loop.run_in_executor(None, functools.partial(subprocess.run, cmd, **kwargs))

# ── 初始化 ──────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bookshare.db"
STORIES_DIR = DATA_DIR / "stories"
STORIES_DIR.mkdir(exist_ok=True)

app = FastAPI()

WEREAD_BASE = "https://weread.qq.com"

STORY_ANGLES = ["书名秘密", "写作故事", "被禁历程", "差点没出版", "角色原型", "作者命运"]

# ── 内置获奖书单 ───────────────────────────────────────────────────────────────
AWARDS_BOOKS = [
    # 诺贝尔文学奖 2000-2024
    {"title": "灵山", "author": "高行健", "award": "诺贝尔文学奖2000"},
    {"title": "河湾", "author": "V.S.奈保尔", "award": "诺贝尔文学奖2001"},
    {"title": "无命运的人", "author": "凯尔泰斯·伊姆雷", "award": "诺贝尔文学奖2002"},
    {"title": "耻", "author": "J.M.库切", "award": "诺贝尔文学奖2003"},
    {"title": "钢琴教师", "author": "埃尔弗里德·耶利内克", "award": "诺贝尔文学奖2004"},
    {"title": "我的名字叫红", "author": "奥尔罕·帕慕克", "award": "诺贝尔文学奖2006"},
    {"title": "金色笔记", "author": "多丽丝·莱辛", "award": "诺贝尔文学奖2007"},
    {"title": "流浪的星星", "author": "勒克莱齐奥", "award": "诺贝尔文学奖2008"},
    {"title": "呼吸秋千", "author": "赫塔·米勒", "award": "诺贝尔文学奖2009"},
    {"title": "城市与狗", "author": "马里奥·巴尔加斯·略萨", "award": "诺贝尔文学奖2010"},
    {"title": "红高粱家族", "author": "莫言", "award": "诺贝尔文学奖2012"},
    {"title": "逃离", "author": "艾丽丝·门罗", "award": "诺贝尔文学奖2013"},
    {"title": "暗店街", "author": "帕特里克·莫迪亚诺", "award": "诺贝尔文学奖2014"},
    {"title": "切尔诺贝利的祭祷", "author": "阿列克谢耶维奇", "award": "诺贝尔文学奖2015"},
    {"title": "长日将尽", "author": "石黑一雄", "award": "诺贝尔文学奖2017"},
    {"title": "云游", "author": "奥尔加·托卡尔丘克", "award": "诺贝尔文学奖2018"},
    {"title": "天堂", "author": "阿卜杜勒拉扎克·古尔纳", "award": "诺贝尔文学奖2021"},
    {"title": "悠悠岁月", "author": "安妮·埃尔诺", "award": "诺贝尔文学奖2022"},
    {"title": "素食者", "author": "韩江", "award": "诺贝尔文学奖2024"},
    # 布克奖 2000-2024
    {"title": "盲刺客", "author": "玛格丽特·阿特伍德", "award": "布克奖2000"},
    {"title": "少年Pi的奇幻漂流", "author": "扬·马特尔", "award": "布克奖2002"},
    {"title": "白虎", "author": "阿拉文德·阿迪加", "award": "布克奖2008"},
    {"title": "狼厅", "author": "希拉里·曼特尔", "award": "布克奖2009"},
    {"title": "终结的感觉", "author": "朱利安·巴恩斯", "award": "布克奖2011"},
    {"title": "发光体", "author": "埃莉诺·卡顿", "award": "布克奖2013"},
    {"title": "七杀简史", "author": "马隆·詹姆斯", "award": "布克奖2015"},
    {"title": "林肯在中阴", "author": "乔治·桑德斯", "award": "布克奖2017"},
    {"title": "送奶工", "author": "安娜·伯恩斯", "award": "布克奖2018"},
    {"title": "沙基", "author": "道格拉斯·斯图尔特", "award": "布克奖2020"},
    {"title": "应许之地", "author": "戴蒙·加尔格特", "award": "布克奖2021"},
    {"title": "预言", "author": "保罗·林奇", "award": "布克奖2023"},
    {"title": "轨道", "author": "萨曼莎·哈维", "award": "布克奖2024"},
]

# ── 一键发现故事 Prompt ───────────────────────────────────────────────────────
DISCOVER_STORY_PROMPT = """你是内容策划+脚本写手，专门制作「书背后的故事」抖音短视频系列。

给你一本书的背景资料，你需要：

1. 找出这本书最有意思、最吸引眼球的一个故事角度
   从以下6个中选1个：书名秘密 / 写作故事 / 被禁历程 / 差点没出版 / 角色原型 / 作者命运

2. 判断标准：要有真实细节（时间、地点、数字、人名），有戏剧性转折，让人有「哇，我不知道这个」的冲击感。
   绝不能是泛泛介绍，要有具体事实支撑。

3. 基于此角度写抖音口播脚本，节奏结构如下：

   ▸ 钩子（前2句，约5秒）：反常识结论或强烈悬念，让划走的手指停下来。
     例：「这本书被五家出版社退稿，作者一气之下差点把手稿付之一炬。」
   ▸ 递进（中间主体，约25-35秒）：用具体细节一层一层揭开故事，有时间/地点/数字，越具体越好。
     每隔几句抛一个小悬念或转折，保持节奏。
   ▸ 收尾（最后1-2句，约5秒）：情感升华或反转呼应开头，让人回味。

   格式要求：
   - 纯口语，连贯自然，适合TTS直接朗读，不要分段标注、不要括号指导语
   - 总字数120-250字（对应30-50秒）
   - 不要分行/分段，写成一段连续口播文本

书籍信息：《{title}》
作者：{author}

原始资料：
{raw_content}

严格返回JSON（不要其他内容）：
{{"angle": "<选定的角度名>", "facts": ["<关键事实1>", "<关键事实2>", "<关键事实3>", "<关键事实4>", "<关键事实5>"], "script": "<完整脚本内容>"}}"""

# ── 数据库 ────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_get_story(story_id: int):
    """从 DB 查询 story + book 连接行，返回 Row 对象。"""
    c = get_db()
    row = c.execute(
        "SELECT s.*, b.title as book_title, b.author as book_author, "
        "b.cover as book_cover "
        "FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?",
        (story_id,)
    ).fetchone()
    c.close()
    return row

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS books (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            weread_id           TEXT UNIQUE NOT NULL,
            title               TEXT NOT NULL,
            author              TEXT,
            cover               TEXT,
            intro               TEXT,
            quotes_fetched      INTEGER DEFAULT 0,
            status              TEXT DEFAULT '待处理',
            story_score         INTEGER,
            story_score_reason  TEXT,
            book_pipeline_status TEXT DEFAULT 'unscored',
            created_at          TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS quotes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
            content    TEXT NOT NULL,
            mark_count INTEGER DEFAULT 0,
            chapter    TEXT,
            ai_score   INTEGER,
            ai_reason  TEXT,
            status     TEXT DEFAULT '收录',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS stories (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id          INTEGER REFERENCES books(id) ON DELETE CASCADE,
            angle            TEXT NOT NULL,
            research_raw     TEXT,
            research_summary TEXT,
            script           TEXT,
            assets           TEXT DEFAULT '[]',
            audio_path       TEXT,
            video_path       TEXT,
            status           TEXT DEFAULT 'pending_research',
            douyin_url       TEXT,
            created_at       TEXT DEFAULT (datetime('now','localtime')),
            updated_at       INTEGER
        );
    """)
    conn.commit()
    conn.close()

def migrate_db():
    """Add new columns to existing tables (idempotent)."""
    conn = get_db()
    migrations = [
        ("books", "story_score", "INTEGER"),
        ("books", "story_score_reason", "TEXT"),
        ("books", "book_pipeline_status", "TEXT DEFAULT 'unscored'"),
        ("books", "intro", "TEXT"),
        ("books", "book_type", "TEXT DEFAULT 'classic'"),
        ("stories", "daily_date", "TEXT"),
        ("stories", "error_msg", "TEXT"),
        ("stories", "updated_at", "INTEGER"),
        ("stories", "cover_path", "TEXT"),
    ]
    for table, col, typedef in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass  # Column already exists
    conn.close()

init_db()
migrate_db()

# ── 微信读书 API ───────────────────────────────────────────────────────────────
def parse_cookies(cookie_str: str) -> dict:
    result = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result

def weread_headers() -> dict:
    cookies = cfg("WEREAD_COOKIES")
    return {
        "Cookie": cookies,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://weread.qq.com/",
        "Origin": "https://weread.qq.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

async def weread_get(url: str, params: dict = None) -> dict:
    headers = weread_headers()
    if not headers["Cookie"]:
        raise HTTPException(400, "WEREAD_COOKIES 未配置，请编辑 .env 文件")
    cookie_dict = parse_cookies(headers["Cookie"])
    extra = {}
    if "wr_vid" in cookie_dict:
        extra["vid"] = cookie_dict["wr_vid"]
    if "wr_skey" in cookie_dict:
        extra["skey"] = cookie_dict["wr_skey"]
    merged_params = {**extra, **(params or {})}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        r = await client.get(f"{WEREAD_BASE}{url}", params=merged_params, headers=headers)
    print(f"[weread] GET {url} → {r.status_code}  body: {r.text[:400]}", flush=True)
    if r.status_code != 200:
        raise HTTPException(502, f"微信读书 API 错误: {r.status_code}，响应: {r.text[:200]}")
    data = r.json()
    if isinstance(data, dict) and data.get("errcode") and data["errcode"] != 0:
        raise HTTPException(401, f"微信读书拒绝 errcode={data['errcode']}：{data.get('errmsg','')}（Cookie 可能已过期）")
    return data

@app.get("/api/weread/test")
async def api_weread_test():
    data = await weread_get("/web/shelf/friendCommon", {"limit": 1})
    return {"ok": True, "raw": data}

# ── Kimi 通用调用 ─────────────────────────────────────────────────────────────
async def kimi_chat(prompt: str, temperature: float = 1) -> str:
    api_key = cfg("KIMI_API_KEY")
    model = cfg("KIMI_MODEL", "kimi-k2.5")
    if not api_key:
        raise HTTPException(400, "请先配置 KIMI_API_KEY")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "disabled"},  # 禁用thinking，响应更快稳定
    }
    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                r = await client.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
            if r.status_code == 400:
                err = r.json().get("error", {})
                # content_filter 不重试，直接抛出
                raise HTTPException(400, f"Kimi拒绝请求: {err.get('message', r.text[:100])}")
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")
            return r.json()["choices"][0]["message"]["content"].strip()
        except HTTPException:
            raise  # 不重试
        except Exception as e:
            last_err = e
            print(f"[kimi] 第{attempt+1}次失败: {e}，{'重试…' if attempt < 2 else '放弃'}", flush=True)
            if attempt < 2:
                await asyncio.sleep(3)
    raise HTTPException(502, f"Kimi API 失败（3次）: {last_err}")

def parse_json_response(text: str) -> dict:
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return json.loads(text.strip())

# ── 封面生成（Pillow，基于 cover_ref.jpg）───────────────────────────────────
COVER_REF_PATH = Path("cover_ref.jpg")
COVER_TARGET_W, COVER_TARGET_H = 1080, 1920
_CN_FONT_CANDIDATES = [
    "/System/Library/Fonts/Songti.ttc",          # 宋体，有衬线，更典雅艺术
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]

def _load_cn_font(size: int):
    from PIL import ImageFont
    for path in _CN_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def make_cover_image(title: str, author: str) -> bytes:
    """用 cover_ref.jpg 裁剪成竖屏，印上书名和作者，返回 JPEG bytes。"""
    from PIL import Image, ImageDraw
    import io

    if not COVER_REF_PATH.exists():
        raise FileNotFoundError("cover_ref.jpg 不存在，请放置在项目根目录")

    img = Image.open(COVER_REF_PATH).convert("RGB")
    src_w, src_h = img.size

    # 等比缩放：以高度为基准填满目标竖屏
    scale = max(COVER_TARGET_W / src_w, COVER_TARGET_H / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # 取最左边裁剪
    left = 0
    top  = (new_h - COVER_TARGET_H) // 2
    img = img.crop((left, top, left + COVER_TARGET_W, top + COVER_TARGET_H))

    # 轻微暗化遮罩：仅底部文字区域，保留原图色彩
    mask = Image.new("L", (COVER_TARGET_W, COVER_TARGET_H), 0)
    mask_draw = ImageDraw.Draw(mask)
    fade_start = int(COVER_TARGET_H * 0.45)  # 从 45% 处开始
    for y in range(fade_start, COVER_TARGET_H):
        alpha = int(90 * ((y - fade_start) / (COVER_TARGET_H - fade_start)) ** 1.2)
        mask_draw.line([(0, y), (COVER_TARGET_W, y)], fill=min(alpha, 90))
    dark = Image.new("RGB", (COVER_TARGET_W, COVER_TARGET_H), (0, 0, 0))
    img = Image.composite(dark, img, mask)

    draw = ImageDraw.Draw(img)

    # 根据书名长度自动选择字号
    title_len = len(title)
    title_size = 100 if title_len <= 6 else (86 if title_len <= 10 else 72)
    title_font  = _load_cn_font(title_size)
    author_font = _load_cn_font(40)
    sep_font    = _load_cn_font(28)

    cx = COVER_TARGET_W // 2
    title_y = COVER_TARGET_H - 720  # 距底部约 720px，偏上

    # 半透明底板（衬托书名）
    panel_pad_x, panel_pad_y = 60, 28
    # 粗略估算文字高度
    title_h_est = title_size + 12
    panel_top    = title_y - panel_pad_y
    panel_bottom = title_y + title_h_est + panel_pad_y
    panel_layer  = Image.new("RGBA", img.size + (None,) if False else (COVER_TARGET_W, COVER_TARGET_H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel_layer)
    pd.rectangle(
        [(panel_pad_x, panel_top), (COVER_TARGET_W - panel_pad_x, panel_bottom)],
        fill=(0, 0, 0, 110)
    )
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, panel_layer)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    # 书名阴影 + 正文
    display_title = f"《{title}》"
    shadow_off = 3
    draw.text((cx + shadow_off, title_y + shadow_off), display_title,
              font=title_font, fill=(0, 0, 0, 160), anchor="mt")
    draw.text((cx, title_y), display_title,
              font=title_font, fill=(255, 245, 210), anchor="mt")

    # 装饰横线
    line_y = title_y + title_h_est + 22
    line_half = 60
    draw.line([(cx - line_half, line_y), (cx + line_half, line_y)],
              fill=(200, 170, 100), width=1)

    # 作者
    if author:
        draw.text((cx, line_y + 18), author,
                  font=author_font, fill=(210, 185, 135), anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()

# ── TTS 设置 ──────────────────────────────────────────────────────────────────
TTS_SETTINGS_PATH = DATA_DIR / "tts_settings.json"
TTS_SETTINGS_DEFAULT = {
    "speed_ratio": 1.08,   # 语速 0.8慢 ~ 1.3快
    "pitch_ratio": 1.0,    # 音调 0.8低沉 ~ 1.2高亮
    "volume_ratio": 1.0,   # 音量
    "silence_s": 0.6,      # 首句后停顿（秒）
}

def load_tts_settings() -> dict:
    try:
        s = json.loads(TTS_SETTINGS_PATH.read_text())
        return {**TTS_SETTINGS_DEFAULT, **s}
    except Exception:
        return dict(TTS_SETTINGS_DEFAULT)

@app.get("/api/tts-settings")
async def api_get_tts_settings():
    return load_tts_settings()

class TtsSettingsBody(BaseModel):
    speed_ratio: float
    pitch_ratio: float
    volume_ratio: float
    silence_s: float

@app.post("/api/tts-settings")
async def api_save_tts_settings(body: TtsSettingsBody):
    s = {
        "speed_ratio":  round(max(0.5, min(2.0, body.speed_ratio)), 2),
        "pitch_ratio":  round(max(0.5, min(2.0, body.pitch_ratio)), 2),
        "volume_ratio": round(max(0.1, min(3.0, body.volume_ratio)), 2),
        "silence_s":    round(max(0.0, min(3.0, body.silence_s)), 2),
    }
    TTS_SETTINGS_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2))
    return {"ok": True, "settings": s}

# ── Kimi 金句打分 ─────────────────────────────────────────────────────────────
SCORE_PROMPT = """你是一个短视频文案专家，专门为书籍金句类短视频账号筛选内容。
请对以下书籍金句进行评分（1-10分），评估维度：
1. 情感共鸣（3分）：能否触动普通读者内心
2. 传播力（3分）：易于理解、适合转发或引用
3. 视觉适合度（2分）：适合做成文字视频展示，长度和风格合适
4. 普适性（2分）：受众广泛，非小众话题

请严格返回 JSON 格式（不要有其他内容）：
{{"score": <整数1-10>, "reason": "<中文简短理由，20字以内>"}}

书籍：{title}（{author}）
金句：{content}"""

async def kimi_score_quote(content: str, title: str, author: str) -> dict:
    api_key = cfg("KIMI_API_KEY")
    if not api_key:
        raise HTTPException(400, "请先配置 KIMI_API_KEY")
    prompt = SCORE_PROMPT.format(title=title, author=author or "未知", content=content)
    text = await kimi_chat(prompt, temperature=1)
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        return {"score": 5, "reason": "解析失败"}

# ── 故事潜力评分 Prompt ───────────────────────────────────────────────────────
STORY_POTENTIAL_PROMPT = """你是一个短视频内容策划专家，专门评估书籍是否有适合制作「书背后的故事」系列短视频的潜力。

请从以下4个维度对这本书进行评分：
1. 写作/出版戏剧性（0-3分）：写作过程、出版经历是否有戏剧性故事
2. 被禁/审查历史（0-3分）：是否有被禁、受审查、引发争议的历史
3. 书名特殊来历（0-2分）：书名是否有特殊含义、有趣来历
4. 作者命运戏剧性（0-2分）：作者生平是否有戏剧性经历

综合评分 = 四个维度之和（0-10分）

请严格返回 JSON 格式（不要有其他内容）：
{{"score": <整数0-10>, "reason": "<评分理由，100字以内>", "angles": ["<最有潜力的2-3个角度，从书名秘密/写作故事/被禁历程/差点没出版/角色原型/作者命运中选择>"]}}

书籍：{title}
作者：{author}
简介：{intro}"""

RESEARCH_SUMMARY_PROMPT = """你是一个内容研究员，请基于以下原始资料，为短视频脚本提炼关键事实。

书籍：《{title}》
作者：{author}
故事角度：{angle}

原始资料：
{raw_content}

请提炼出5个最有价值的关键事实，用于「{angle}」角度的短视频脚本创作。
每个事实要求：具体、有细节、可验证、有戏剧性。

严格返回 JSON 格式：
{{"facts": ["<事实1>", "<事实2>", "<事实3>", "<事实4>", "<事实5>"], "summary": "<200字以内的综合叙述>"}}"""

SCRIPT_PROMPTS = {
    "书名秘密": "书名的来历、隐藏含义、作者取名的故事",
    "写作故事": "作者写作时的处境、困难、花费的时间、特殊经历",
    "被禁历程": "被哪些国家/机构禁止、禁止的原因、禁止后的命运",
    "差点没出版": "出版过程中的波折、被多少出版商拒绝、最终如何出版",
    "角色原型": "书中角色的现实原型、作者如何塑造人物、真实故事",
    "作者命运": "作者的人生经历、命运转折、与书的关系",
}

SCRIPT_TEMPLATE = """你是一位抖音口播脚本写手，专门制作「书背后的故事」系列短视频。

请基于以下研究素材，为书籍《{title}》（作者：{author}）写一段「{angle}」角度的抖音口播脚本。

角度重点：{angle_focus}

节奏结构（不要在脚本里写出这些标签，只是内部参考）：
▸ 钩子（前2句，约5秒）：反常识结论或强烈悬念，让划走的手指停下来
▸ 递进（中间主体，约25-35秒）：具体细节逐层揭开，含时间/地点/数字/人名，每隔几句抛出小悬念维持张力
▸ 收尾（最后1-2句，约5秒）：情感升华或反转呼应开头，留有余味

格式要求：
- 纯口语，连贯自然，适合TTS直接朗读
- 总字数120-250字（对应30-50秒）
- 不分段、不分行、不加任何标注，写成一段连续文本
- 不要任何括号说明或舞台指导

研究素材：
{research}

请直接输出脚本文本，不要有其他说明。"""

def add_script_intro(script: str, title: str) -> str:
    """在脚本开头加固定引导语（如果还没有的话）。"""
    intro = f"一天介绍一个书籍背后的故事，今天讲的是《{title}》。"
    script = script.strip()
    if script.startswith(intro):
        return script
    return intro + script

# ── Pydantic Models ───────────────────────────────────────────────────────────
class BookStatusIn(BaseModel):
    status: str

class QuoteStatusIn(BaseModel):
    status: str

class ManualBookIn(BaseModel):
    weread_id: str
    title: str
    author: Optional[str] = None
    cover: Optional[str] = None

class StoryCreateIn(BaseModel):
    book_id: int
    angle: str

class StoryScriptIn(BaseModel):
    script: str

class StoryStatusIn(BaseModel):
    status: str

class DouyinUrlIn(BaseModel):
    douyin_url: str

# ── API 路由：书单 ─────────────────────────────────────────────────────────────
@app.get("/api/books")
def api_list_books(status: Optional[str] = None):
    conn = get_db()
    sql = """SELECT b.*,
             (SELECT COUNT(*) FROM quotes q WHERE q.book_id=b.id) as quote_count,
             (SELECT COUNT(*) FROM stories s WHERE s.book_id=b.id) as story_count,
             (SELECT COUNT(*) FROM stories s WHERE s.book_id=b.id AND s.status NOT IN ('pending_research','failed')) as researched_count,
             (SELECT id FROM stories s WHERE s.book_id=b.id ORDER BY s.created_at DESC LIMIT 1) as latest_story_id,
             (SELECT status FROM stories s WHERE s.book_id=b.id ORDER BY s.created_at DESC LIMIT 1) as latest_story_status
             FROM books b WHERE 1=1"""
    params = []
    if status:
        sql += " AND b.status=?"
        params.append(status)
    sql += " ORDER BY b.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/books/search")
async def api_search_books(keyword: str):
    data = await weread_get(
        "/web/search/global",
        {"keyword": keyword, "count": 20, "fragmentSize": 120},
    )
    raw_books = data.get("books", data.get("items", []))
    result = []
    for item in raw_books:
        b = item.get("bookInfo", item)
        bid = b.get("bookId", "")
        if not bid:
            continue
        result.append({
            "weread_id": bid,
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "cover": b.get("cover", ""),
            "intro": b.get("intro", ""),
        })
    return result

@app.post("/api/books")
def api_add_book(body: ManualBookIn):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO books(weread_id,title,author,cover) VALUES(?,?,?,?)",
            (body.weread_id, body.title, body.author, body.cover)
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.patch("/api/books/{book_id}/status")
def api_update_book_status(book_id: int, body: BookStatusIn):
    conn = get_db()
    conn.execute("UPDATE books SET status=? WHERE id=?", (body.status, book_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/books/{book_id}/fetch")
async def api_fetch_quotes(book_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "书籍不存在")

    book_id_str = row["weread_id"]
    all_items = []
    offset = 0
    page_size = 100
    while True:
        data = await weread_get("/web/book/bookmarklist", {
            "bookId": book_id_str, "offset": offset,
            "count": page_size, "sortType": 0,
        })
        payload = data.get("bookmarkList", data)
        if isinstance(payload, list):
            page_items = payload
        else:
            page_items = payload.get("items", payload.get("updated", []))
        all_items.extend(page_items)
        if len(page_items) < page_size:
            break
        offset += len(page_items)
        await asyncio.sleep(0.3)

    if not all_items:
        data = await weread_get("/web/book/bestbookmarks", {"bookId": book_id_str, "synckey": 0, "count": 500})
        payload = data.get("bestBookMarks", data)
        all_items = payload.get("items", [])

    items = all_items
    chapter_map = {}
    if isinstance(payload, dict):
        for ch in payload.get("chapters", []):
            chapter_map[ch.get("chapterUid")] = ch.get("title", "")

    conn = get_db()
    count = 0
    for item in items:
        content = item.get("markText", "").strip()
        if not content:
            continue
        mark_count = item.get("totalCount", item.get("markCount", 0))
        chapter_uid = item.get("chapterUid")
        chapter = chapter_map.get(chapter_uid, item.get("chapterTitle", ""))
        exists = conn.execute(
            "SELECT id FROM quotes WHERE book_id=? AND content=?", (book_id, content)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO quotes(book_id,content,mark_count,chapter) VALUES(?,?,?,?)",
                (book_id, content, mark_count, chapter)
            )
            count += 1
    conn.execute("UPDATE books SET quotes_fetched=1 WHERE id=?", (book_id,))
    conn.commit()
    conn.close()
    total = payload.get("totalCount", len(items)) if isinstance(payload, dict) else len(items)
    return {"ok": True, "new_quotes": count, "total": total}

@app.post("/api/books/{book_id}/score")
async def api_score_quotes(book_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    unscored = conn.execute(
        "SELECT id, content FROM quotes WHERE book_id=? AND ai_score IS NULL", (book_id,)
    ).fetchall()
    conn.close()
    if not book:
        raise HTTPException(404, "书籍不存在")
    if not unscored:
        return {"ok": True, "message": "没有待打分的金句"}

    async def do_score():
        title = book["title"]
        author = book["author"] or ""
        for q in unscored:
            try:
                result = await kimi_score_quote(q["content"], title, author)
                score = result.get("score", 5)
                reason = result.get("reason", "")
                c = get_db()
                c.execute("UPDATE quotes SET ai_score=?, ai_reason=? WHERE id=?",
                          (score, reason, q["id"]))
                c.commit(); c.close()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"打分失败 quote_id={q['id']}: {e}", flush=True)

    background_tasks.add_task(do_score)
    return {"ok": True, "queued": len(unscored)}

# ── API 路由：金句 ─────────────────────────────────────────────────────────────
@app.get("/api/quotes")
def api_list_quotes(
    book_id: Optional[int] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
):
    conn = get_db()
    sql = """SELECT q.*, b.title as book_title, b.author as book_author
             FROM quotes q JOIN books b ON q.book_id = b.id WHERE 1=1"""
    params = []
    if book_id:
        sql += " AND q.book_id=?"
        params.append(book_id)
    if status:
        sql += " AND q.status=?"
        params.append(status)
    if min_score is not None:
        sql += " AND q.ai_score>=?"
        params.append(min_score)
    sql += " ORDER BY q.mark_count DESC, q.ai_score DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.patch("/api/quotes/{quote_id}/status")
def api_update_quote_status(quote_id: int, body: QuoteStatusIn):
    valid = {"收录", "待制作", "已制作", "跳过"}
    if body.status not in valid:
        raise HTTPException(400, f"无效状态，可选：{valid}")
    conn = get_db()
    conn.execute("UPDATE quotes SET status=? WHERE id=?", (body.status, quote_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.patch("/api/quotes/batch-status")
def api_batch_quote_status(body: dict):
    ids = body.get("ids", [])
    status = body.get("status", "")
    valid = {"收录", "待制作", "已制作", "跳过"}
    if status not in valid or not ids:
        raise HTTPException(400, "参数错误")
    conn = get_db()
    conn.execute(
        f"UPDATE quotes SET status=? WHERE id IN ({','.join('?'*len(ids))})",
        [status] + ids
    )
    conn.commit()
    conn.close()
    return {"ok": True, "updated": len(ids)}

# ── API 路由：导出 / 统计 ──────────────────────────────────────────────────────
@app.get("/api/export")
def api_export(status: Optional[str] = None):
    conn = get_db()
    sql = """SELECT q.id, b.title as book_title, b.author as book_author,
                    q.chapter, q.content, q.mark_count, q.ai_score, q.ai_reason, q.status
             FROM quotes q JOIN books b ON q.book_id = b.id
             WHERE q.status != '跳过'"""
    params = []
    if status:
        sql += " AND q.status=?"
        params.append(status)
    sql += " ORDER BY q.ai_score DESC, q.mark_count DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(rows),
        "quotes": [dict(r) for r in rows],
    }
    return JSONResponse(result, headers={"Content-Disposition": 'attachment; filename="quotes.json"'})

@app.get("/api/stats")
def api_stats():
    conn = get_db()
    book_stats = {row["status"]: row["cnt"] for row in conn.execute(
        "SELECT status, COUNT(*) as cnt FROM books GROUP BY status"
    ).fetchall()}
    quote_stats = {row["status"]: row["cnt"] for row in conn.execute(
        "SELECT status, COUNT(*) as cnt FROM quotes GROUP BY status"
    ).fetchall()}
    conn.close()
    return {"books": book_stats, "quotes": quote_stats}

# ══════════════════════════════════════════════════════════════════════════════
# 故事流水线
# ══════════════════════════════════════════════════════════════════════════════

# ── 故事潜力评分 ──────────────────────────────────────────────────────────────
@app.post("/api/books/{book_id}/score-story-potential")
async def api_score_story_potential(book_id: int):
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    conn.close()
    if not book:
        raise HTTPException(404, "书籍不存在")
    prompt = STORY_POTENTIAL_PROMPT.format(
        title=book["title"],
        author=book["author"] or "未知",
        intro=book["intro"] or "暂无简介",
    )
    text = await kimi_chat(prompt, temperature=1)
    try:
        result = parse_json_response(text)
        score = int(result.get("score", 5))
        reason = result.get("reason", "")
        angles = result.get("angles", [])
        pipeline_status = "ready" if score >= 6 else "low_potential"
        conn = get_db()
        conn.execute(
            "UPDATE books SET story_score=?, story_score_reason=?, book_pipeline_status=? WHERE id=?",
            (score, reason, pipeline_status, book_id)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "score": score, "reason": reason, "angles": angles, "status": pipeline_status}
    except Exception as e:
        raise HTTPException(502, f"解析响应失败: {e}，原文: {text[:200]}")

# ── 选题建议 ──────────────────────────────────────────────────────────────────
@app.post("/api/stories/suggest")
async def api_suggest_angles(body: dict):
    book_id = body.get("book_id")
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if not book:
        conn.close()
        raise HTTPException(404, "书籍不存在")
    existing = conn.execute("SELECT angle FROM stories WHERE book_id=?", (book_id,)).fetchall()
    conn.close()
    used = {r["angle"] for r in existing}
    available = [a for a in STORY_ANGLES if a not in used]
    if not available:
        available = STORY_ANGLES  # all angles used, allow repeats

    prompt = f"""你是短视频内容策划，请为书籍《{book["title"]}》（作者：{book["author"] or "未知"}）推荐最适合制作「书背后的故事」短视频的角度。

可选角度：{', '.join(available)}

请推荐1-3个最有潜力的角度，并说明理由。

严格返回 JSON：
{{"suggestions": [{{"angle": "<角度>", "reason": "<50字理由>", "hook": "<一句话钩子示例>"}}]}}"""

    text = await kimi_chat(prompt, temperature=1)
    try:
        result = parse_json_response(text)
        return {"ok": True, "book": dict(book), "suggestions": result.get("suggestions", [])}
    except Exception as e:
        raise HTTPException(502, f"解析失败: {e}")

# ── 流水线总览 ─────────────────────────────────────────────────────────────────
@app.get("/api/pipeline")
def api_pipeline():
    conn = get_db()
    books = conn.execute(
        """SELECT id, title, author, cover, story_score, story_score_reason, book_pipeline_status
           FROM books
           WHERE story_score IS NOT NULL OR book_pipeline_status != 'unscored'
           ORDER BY story_score DESC"""
    ).fetchall()
    result = []
    for b in books:
        stats = {}
        for st in ["pending_research", "researching", "research_done", "scripting",
                   "script_draft", "script_approved", "producing", "done", "published"]:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE book_id=? AND status=?", (b["id"], st)
            ).fetchone()[0]
            if cnt:
                stats[st] = cnt
        result.append({**dict(b), "story_stats": stats})
    conn.close()
    return result

@app.get("/api/pipeline/stories")
def api_pipeline_stories(status: Optional[str] = None):
    conn = get_db()
    sql = """SELECT s.*, b.title as book_title, b.author as book_author, b.cover as book_cover
             FROM stories s JOIN books b ON s.book_id = b.id WHERE 1=1"""
    params = []
    if status:
        sql += " AND s.status=?"
        params.append(status)
    sql += " ORDER BY s.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── 故事 CRUD ─────────────────────────────────────────────────────────────────
@app.get("/api/stories")
def api_list_stories(book_id: Optional[int] = None, status: Optional[str] = None):
    conn = get_db()
    sql = """SELECT s.*, b.title as book_title, b.author as book_author, b.cover as book_cover
             FROM stories s JOIN books b ON s.book_id = b.id WHERE 1=1"""
    params = []
    if book_id:
        sql += " AND s.book_id=?"
        params.append(book_id)
    if status:
        sql += " AND s.status=?"
        params.append(status)
    sql += " ORDER BY s.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/stories")
def api_create_story(body: StoryCreateIn):
    if body.angle not in STORY_ANGLES:
        raise HTTPException(400, f"无效角度，可选：{STORY_ANGLES}")
    conn = get_db()
    book = conn.execute("SELECT id FROM books WHERE id=?", (body.book_id,)).fetchone()
    if not book:
        conn.close()
        raise HTTPException(404, "书籍不存在")
    cur = conn.execute(
        "INSERT INTO stories(book_id, angle, status) VALUES(?,?,?)",
        (body.book_id, body.angle, "pending_research")
    )
    story_id = cur.lastrowid
    conn.commit()
    conn.close()
    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "assets").mkdir(exist_ok=True)
    return {"ok": True, "id": story_id}

@app.get("/api/stories/{story_id}")
def api_get_story(story_id: int):
    conn = get_db()
    row = conn.execute(
        """SELECT s.*, b.title as book_title, b.author as book_author, b.cover as book_cover
           FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?""",
        (story_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")
    return dict(row)

@app.patch("/api/stories/{story_id}/script")
def api_update_script(story_id: int, body: StoryScriptIn):
    conn = get_db()
    conn.execute("UPDATE stories SET script=? WHERE id=?", (body.script, story_id))
    conn.commit()
    conn.close()
    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "script_draft.txt").write_text(body.script, encoding="utf-8")
    return {"ok": True}

@app.patch("/api/stories/{story_id}/status")
def api_update_story_status(story_id: int, body: StoryStatusIn):
    conn = get_db()
    conn.execute("UPDATE stories SET status=? WHERE id=?", (body.status, story_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.patch("/api/stories/{story_id}/douyin")
def api_update_douyin(story_id: int, body: DouyinUrlIn):
    conn = get_db()
    conn.execute(
        "UPDATE stories SET douyin_url=?, status='published' WHERE id=?",
        (body.douyin_url, story_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/stories/{story_id}")
def api_delete_story(story_id: int):
    conn = get_db()
    conn.execute("DELETE FROM stories WHERE id=?", (story_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# ── 研究引擎 ──────────────────────────────────────────────────────────────────
def strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:8000]

async def brave_search(query: str) -> list:
    api_key = cfg("BRAVE_API_KEY")
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                params={"q": query, "count": 5},
            )
        if r.status_code != 200:
            print(f"[brave] {r.status_code}: {r.text[:200]}", flush=True)
            return []
        return r.json().get("web", {}).get("results", [])
    except Exception as e:
        print(f"[brave] error: {e}", flush=True)
        return []

async def fetch_page_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(url)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return strip_html(r.text)
    except Exception as e:
        print(f"[fetch] {url}: {e}", flush=True)
    return ""

async def wikipedia_extract(title: str, lang: str = "zh") -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query", "titles": title, "prop": "extracts",
                    "exintro": 1, "explaintext": 1, "format": "json",
                },
            )
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            if extract and not extract.startswith("指"):
                return extract[:3000]
    except Exception as e:
        print(f"[wiki] {lang}/{title}: {e}", flush=True)
    return ""

@app.post("/api/stories/{story_id}/research")
async def api_research(story_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, b.title, b.author FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?",
        (story_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")

    async def do_research():
        title = row["title"]
        author = row["author"] or ""
        angle = row["angle"]
        print(f"[research] ▶ 开始 story={story_id} 《{title}》角度={angle}", flush=True)

        c = get_db()
        c.execute("UPDATE stories SET status='researching' WHERE id=?", (story_id,))
        c.commit(); c.close()

        raw_data = {"searches": [], "wikipedia": {}, "pages": []}

        # 1. Brave Search（三轮查询）
        queries = [
            f"{title} {author} {angle}",
            f"{title} {author} story behind",
            f"《{title}》{angle} 背后故事",
        ]
        for q in queries:
            results = await brave_search(q)
            for item in results[:2]:
                page_text = await fetch_page_text(item.get("url", ""))
                raw_data["searches"].append({
                    "query": q, "title": item.get("title"), "url": item.get("url"),
                    "description": item.get("description", ""), "text": page_text[:2000],
                })
            await asyncio.sleep(0.3)

        # 2. Wikipedia（中英文）
        for lang, search_title in [("zh", title), ("en", title), ("zh", author), ("en", author)]:
            if not search_title:
                continue
            extract = await wikipedia_extract(search_title, lang)
            if extract:
                raw_data["wikipedia"][f"{lang}:{search_title}"] = extract

        # 保存原始数据
        story_dir = STORIES_DIR / str(story_id)
        story_dir.mkdir(exist_ok=True)
        (story_dir / "research_raw.json").write_text(
            json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 3. Kimi 提炼关键事实
        combined = ""
        for s in raw_data["searches"]:
            if s["text"]:
                combined += f"\n--- 来源: {s['title']} ---\n{s['text']}\n"
        for k, v in raw_data["wikipedia"].items():
            combined += f"\n--- Wikipedia ({k}) ---\n{v}\n"

        if combined.strip():
            prompt = RESEARCH_SUMMARY_PROMPT.format(
                title=title, author=author, angle=angle,
                raw_content=combined[:12000],
            )
            try:
                kimi_text = await kimi_chat(prompt, temperature=1)
                summary = parse_json_response(kimi_text)
            except Exception as e:
                summary = {"facts": [combined[:500]], "summary": combined[:500], "error": str(e)}
        else:
            summary = {"facts": [], "summary": "未找到相关资料，请手动补充。"}

        (story_dir / "research_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        c = get_db()
        c.execute(
            "UPDATE stories SET research_raw=?, research_summary=?, status='scripting' WHERE id=?",
            (json.dumps(raw_data, ensure_ascii=False),
             json.dumps(summary, ensure_ascii=False), story_id)
        )
        c.commit(); c.close()
        print(f"[research] story {story_id} done，自动开始生成脚本…", flush=True)

        # ── 自动接续生成脚本 ──────────────────────────────────────────────
        facts = summary.get("facts", [])
        research_text = summary.get("summary", "") + "\n\n关键事实：\n" + "\n".join(f"- {f}" for f in facts)
        prompt = SCRIPT_TEMPLATE.format(
            title=title, author=author or "未知",
            angle=angle,
            angle_focus=SCRIPT_PROMPTS.get(angle, angle),
            research=research_text,
        )
        try:
            script = await kimi_chat(prompt)
            script = add_script_intro(script, title)
            (story_dir / "script_draft.txt").write_text(script, encoding="utf-8")
            c = get_db()
            c.execute("UPDATE stories SET script=?, status='script_draft' WHERE id=?", (script, story_id))
            c.commit(); c.close()
            print(f"[script] story {story_id} done", flush=True)
        except Exception as e:
            err = str(e)
            print(f"[script] story {story_id} 生成失败: {err}", flush=True)
            c = get_db()
            c.execute("UPDATE stories SET status='failed', error_msg=? WHERE id=?", (err, story_id))
            c.commit(); c.close()

    background_tasks.add_task(do_research)
    return {"ok": True, "message": "研究+生成脚本已启动，完成后自动进入待审核"}

# ── 脚本生成 ──────────────────────────────────────────────────────────────────
@app.post("/api/stories/{story_id}/generate-script")
async def api_generate_script(story_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, b.title, b.author FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?",
        (story_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")
    if row["status"] not in ("research_done", "script_draft", "script_approved", "producing", "done", "published"):
        raise HTTPException(400, f"当前状态 {row['status']} 无法生成脚本，需先完成研究")

    background_tasks.add_task(_run_generate, story_id)
    return {"ok": True, "message": "脚本生成中，请稍后刷新"}

# ── 脚本审核（强制断点）─────────────────────────────────────────────────────
@app.post("/api/stories/{story_id}/approve-script")
def api_approve_script(story_id: int, body: StoryScriptIn):
    conn = get_db()
    row = conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "故事不存在")
    script = body.script or row["script"] or ""
    conn.execute(
        "UPDATE stories SET script=?, status='script_approved' WHERE id=?",
        (script, story_id)
    )
    conn.commit(); conn.close()
    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "script_approved.txt").write_text(script, encoding="utf-8")
    return {"ok": True}

# ── 素材抓取 ──────────────────────────────────────────────────────────────────
WIKIMEDIA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

async def brave_search_images(query: str, limit: int = 6) -> list:
    api_key = cfg("BRAVE_API_KEY")
    if not api_key:
        print("[brave_img] BRAVE_API_KEY 未配置", flush=True)
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.search.brave.com/res/v1/images/search",
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                params={"q": query, "count": min(limit, 20), "safesearch": "off"},
            )
        print(f"[brave_img] search '{query}' status={r.status_code}", flush=True)
        if r.status_code != 200:
            print(f"[brave_img] 错误响应: {r.text[:200]}", flush=True)
            return []
        results = []
        for item in r.json().get("results", []):
            url = item.get("properties", {}).get("url") or item.get("thumbnail", {}).get("src", "")
            if not url:
                continue
            results.append({
                "title": item.get("title", query),
                "url": url,
                "caption": item.get("title", ""),
            })
        print(f"[brave_img] 找到 {len(results)} 张图", flush=True)
        return results
    except Exception as e:
        print(f"[brave_img] 错误: {e}", flush=True)
        return []


async def search_images(query: str, limit: int = 6) -> list:
    """根据 IMAGE_SEARCH_PROVIDER 配置选择图片来源（wikimedia / brave）"""
    provider = cfg("IMAGE_SEARCH_PROVIDER", "wikimedia").lower()
    if provider == "brave":
        return await brave_search_images(query, limit)
    return await wikimedia_search_images(query, limit)


async def wikimedia_search_images(query: str, limit: int = 6) -> list:
    try:
        async with httpx.AsyncClient(timeout=15, headers=WIKIMEDIA_HEADERS) as client:
            r = await client.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query", "list": "search", "srnamespace": "6",
                    "srsearch": query, "srlimit": limit, "format": "json",
                },
            )
        print(f"[wikimedia] search '{query}' status={r.status_code} len={len(r.text)}", flush=True)
        if not r.text.strip():
            print(f"[wikimedia] 空响应，跳过", flush=True)
            return []
        items = r.json().get("query", {}).get("search", [])
        print(f"[wikimedia] 找到 {len(items)} 条结果", flush=True)
        results = []
        for item in items:
            page_title = item["title"]
            async with httpx.AsyncClient(timeout=10, headers=WIKIMEDIA_HEADERS) as client:
                info_r = await client.get(
                    "https://commons.wikimedia.org/w/api.php",
                    params={
                        "action": "query", "titles": page_title,
                        "prop": "imageinfo", "iiprop": "url|mime|size|thumburl",
                        "iiurlwidth": "800",
                        "format": "json",
                    },
                )
            if not info_r.text.strip():
                continue
            pages = info_r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                info_list = page.get("imageinfo", [])
                if info_list:
                    info = info_list[0]
                    mime = info.get("mime", "")
                    thumb_url = info.get("thumburl") or info.get("url", "")
                    print(f"[wikimedia]   {page_title} mime={mime} thumb={thumb_url[:60]}", flush=True)
                    # 过滤：只要真实照片/绘画；排除 svg、djvu（书页扫描）、pdf
                    is_real_image = (
                        mime.startswith("image/")
                        and not mime.endswith("/svg+xml")
                        and "djvu" not in mime
                        and "pdf" not in mime
                        and "vnd." not in mime  # 排除所有 vnd.* 格式
                    )
                    if is_real_image:
                        results.append({
                            "title": page_title, "url": thumb_url,
                            "mime": "image/jpeg",
                            "caption": item.get("snippet", ""),
                        })
                else:
                    print(f"[wikimedia]   {page_title} 无imageinfo", flush=True)
    except Exception as e:
        print(f"[wikimedia] 错误: {e}", flush=True)
        return []
    return results

@app.post("/api/stories/{story_id}/fetch-assets")
async def api_fetch_assets(story_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, b.title, b.author, b.cover FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?",
        (story_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")

    async def do_fetch():
        asset_dir = STORIES_DIR / str(story_id) / "assets"
        # 清空 DB assets 字段，UI 立刻不显示旧图片
        c = get_db(); c.execute("UPDATE stories SET assets='[]' WHERE id=?", (story_id,)); c.commit(); c.close()
        # 清空整个 assets/ 目录
        import shutil as _shutil
        _shutil.rmtree(str(asset_dir), ignore_errors=True)
        asset_dir.mkdir(parents=True, exist_ok=True)
        assets = []
        title = row["title"]
        author = row["author"] or ""
        script = row["script"] or ""
        angle = row["angle"] or ""

        # 1. 书封面：豆瓣 suggest API（对中文书最准）
        DOUBAN_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://book.douban.com/",
        }
        cover_url = row["cover"]
        if not cover_url and title:
            try:
                async with httpx.AsyncClient(timeout=10, headers=DOUBAN_HEADERS) as client:
                    r = await client.get(
                        "https://book.douban.com/j/subject_suggest",
                        params={"q": title},
                    )
                if r.status_code == 200:
                    items = r.json()
                    # 找最匹配的书（优先书名完全匹配）
                    best = None
                    for item in items:
                        if item.get("type") != "b":
                            continue
                        if item.get("title", "").startswith(title):
                            best = item
                            break
                    if not best and items:
                        best = next((i for i in items if i.get("type") == "b"), None)
                    if best and best.get("pic"):
                        # 把 /s/ 换成 /l/ 拿大图
                        cover_url = best["pic"].replace("/s/public/", "/l/public/")
                        print(f"[assets] 豆瓣封面: {cover_url}", flush=True)
            except Exception as e:
                print(f"[assets] 豆瓣查询失败: {e}", flush=True)

        if cover_url:
            try:
                async with httpx.AsyncClient(timeout=15, headers=DOUBAN_HEADERS,
                                             follow_redirects=True) as client:
                    r = await client.get(cover_url)
                # 检查图片尺寸，太小则放弃用豆瓣，转 Open Library
                cover_too_small = False
                if r.status_code == 200 and len(r.content) > 2000:
                    try:
                        import io
                        from PIL import Image as PILImage
                        img_check = PILImage.open(io.BytesIO(r.content))
                        w, h = img_check.size
                        if w < 400 or h < 400:
                            print(f"[assets] 豆瓣封面过小 {w}x{h}，尝试更好来源", flush=True)
                            cover_too_small = True
                        else:
                            print(f"[assets] 豆瓣封面尺寸 {w}x{h}，可用", flush=True)
                    except Exception:
                        pass
                if r.status_code == 200 and len(r.content) > 2000 and not cover_too_small:
                    cover_bytes = r.content
                    cover_final_url = cover_url
                else:
                    cover_bytes = None
                    cover_final_url = cover_url
            except Exception as e:
                cover_bytes = None
                cover_final_url = cover_url
                print(f"[assets] 豆瓣封面下载失败: {e}", flush=True)

            # Open Library 兜底（适合外文经典书）
            if not cover_bytes and title:
                try:
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        ol = await client.get(
                            "https://openlibrary.org/search.json",
                            params={"title": title, "author": author or "", "limit": 3},
                        )
                    for doc in (ol.json() if ol.text.strip() else {}).get("docs", []):
                        cid = doc.get("cover_i")
                        if not cid:
                            continue
                        ol_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"
                        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                            ol_r = await client.get(ol_url)
                        if ol_r.status_code == 200 and len(ol_r.content) > 10000:
                            cover_bytes = ol_r.content
                            cover_final_url = ol_url
                            print(f"[assets] Open Library封面: {ol_url}", flush=True)
                            break
                except Exception as e:
                    print(f"[assets] Open Library封面失败: {e}", flush=True)

            # Brave Image Search 兜底（豆瓣和 Open Library 都失败时）
            # 用书名精确搜，并验证结果标题包含书名关键词才采用
            if not cover_bytes and title:
                try:
                    # 生成书名的2字连续子串用于宽松匹配（兼容不同音译，如「哈姆莱特」vs「哈姆雷特」）
                    def title_bigrams(t: str) -> list:
                        t2 = re.sub(r'[\s·\-：:《》「」\'"]+', '', t)
                        return [t2[i:i+2] for i in range(len(t2) - 1)] if len(t2) >= 2 else [t2]
                    kw_bigrams = title_bigrams(title)
                    # 英文作者名按空格拆词
                    author_kws = [w.lower() for w in author.split() if len(w) >= 3] if author else []
                    for brave_query in [
                        f'"{title}" 封面',
                        f'"{title}" book cover',
                        f'{title} {author} book cover'.strip(),
                    ]:
                        brave_results = await brave_search_images(brave_query, limit=6)
                        for br in brave_results:
                            # 验证：结果标题/URL 包含书名任意2字连续子串 或 作者名关键词
                            br_combined = (br.get("title", "") + " " + br.get("url", "")).lower()
                            matched = (
                                any(bg in br_combined for bg in kw_bigrams)
                                or any(ak in br_combined for ak in author_kws)
                            )
                            if not matched:
                                print(f"[assets] Brave封面不相关，跳过: {br.get('title','')[:60]}", flush=True)
                                continue
                            try:
                                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                                    br_r = await client.get(br["url"])
                                if br_r.status_code == 200 and len(br_r.content) > 20000:
                                    import io
                                    from PIL import Image as PILImage
                                    img_check = PILImage.open(io.BytesIO(br_r.content))
                                    w, h = img_check.size
                                    if w >= 200 and h >= 200:
                                        cover_bytes = br_r.content
                                        cover_final_url = br["url"]
                                        print(f"[assets] Brave封面: {br['url']} {w}x{h}", flush=True)
                                        break
                            except Exception:
                                continue
                        if cover_bytes:
                            break
                except Exception as e:
                    print(f"[assets] Brave封面失败: {e}", flush=True)

            if cover_bytes:
                cover_path = asset_dir / "00_cover.jpg"
                cover_path.write_bytes(cover_bytes)
                assets.append({"type": "cover", "url": cover_final_url,
                               "local": f"data/stories/{story_id}/assets/00_cover.jpg",
                               "caption": f"《{title}》封面",
                               "keyword": "书封面"})
                print(f"[assets] ✓ 封面已保存 ({len(cover_bytes)//1024}KB)", flush=True)
            else:
                print(f"[assets] 封面获取失败", flush=True)

        # 2. 作者照片/画像（Wikimedia 专项搜索）
        if author:
            author_en = author  # 可能是中文名，也搜英文
            for author_q in [f"{author} portrait", f"{author} photograph", author]:
                imgs = await wikimedia_search_images(author_q, limit=3)
                if imgs:
                    print(f"[assets] 作者图搜「{author_q}」→ {len(imgs)}张", flush=True)
                    img = imgs[0]
                    try:
                        async with httpx.AsyncClient(timeout=30, headers=WIKIMEDIA_HEADERS,
                                                     follow_redirects=True) as client:
                            ir = await client.get(img["url"])
                        if ir.status_code == 200 and len(ir.content) > 5000:
                            safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', author)[:20]
                            local_name = f"01_author_{safe}.jpg"
                            (asset_dir / local_name).write_bytes(ir.content)
                            caption = img.get("title", "").replace("File:", "").split(".")[0] or f"{author}照片"
                            assets.append({"type": "author", "url": img["url"],
                                           "local": f"data/stories/{story_id}/assets/{local_name}",
                                           "caption": caption, "keyword": f"{author}照片"})
                            print(f"[assets] ✓ 作者图已保存 {local_name}", flush=True)
                            break
                    except Exception as e:
                        print(f"[assets] 作者图下载失败: {e}", flush=True)
                    await asyncio.sleep(2)

        # 2. 用 Kimi 从脚本提取搜图关键词
        img_provider = cfg("IMAGE_SEARCH_PROVIDER", "wikimedia").lower()
        search_queries = [author]  # 默认至少搜作者
        if script:
            try:
                if img_provider == "google":
                    kw_hint = "适合在 Google 图片搜索的关键词，可以是具体场景、年代、地点、人物，也可以是能体现故事氛围的意象词。"
                else:
                    kw_hint = "适合在 Wikimedia Commons 搜索的历史档案图片关键词，聚焦脚本中提到的具体人物、地点、事件、时代背景。"
                kw_prompt = f"""根据以下书籍故事脚本，提取3-5个{kw_hint}
要求：英文或中文关键词，不要用书名本身，要用脚本里的具体内容。

书名：《{title}》 作者：{author} 故事角度：{angle}
脚本：{script[:800]}

严格返回JSON：{{"keywords": ["关键词1", "关键词2", "关键词3"]}}"""
                kw_text = await kimi_chat(kw_prompt)
                kw_result = parse_json_response(kw_text)
                kw_list = kw_result.get("keywords", [])
                if kw_list:
                    search_queries = kw_list[:4]
                    print(f"[assets] Kimi搜图关键词({img_provider}): {search_queries}", flush=True)
            except Exception as e:
                print(f"[assets] 关键词提取失败，用默认: {e}", flush=True)

        # 3. 用关键词搜图并下载
        img_idx = 1
        for q in search_queries:
            if not q or img_idx > 5:
                break
            images = await search_images(q, limit=3)
            print(f"[assets] [{img_provider}] 搜「{q}」→ {len(images)} 张", flush=True)
            for img in images[:2]:
                if img_idx > 5:
                    break
                try:
                    async with httpx.AsyncClient(timeout=30, headers=WIKIMEDIA_HEADERS,
                                                 follow_redirects=True) as client:
                        ir = await client.get(img["url"])
                    print(f"[assets]   {img['url'][-50:]} → {ir.status_code}", flush=True)
                    if ir.status_code == 200 and len(ir.content) > 5000:
                        # 尺寸/比例检查：避免保存极窄/极矮的图（如图表、横幅）
                        try:
                            import io as _io
                            from PIL import Image as _PILImg
                            _dim = _PILImg.open(_io.BytesIO(ir.content)).size
                            _w, _h = _dim
                            _ratio = max(_w, _h) / max(min(_w, _h), 1)
                            if _w < 300 or _h < 300 or _ratio > 3.5:
                                print(f"[assets]   ✗ 跳过不适合视频的图 {_w}x{_h} ratio={_ratio:.1f}", flush=True)
                                continue
                        except Exception:
                            pass
                        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', q)[:30]
                        local_name = f"{img_idx:02d}_{safe_name}.jpg"
                        (asset_dir / local_name).write_bytes(ir.content)
                        caption = img.get("title", "").replace("File:", "").split(".")[0] or q
                        assets.append({
                            "type": img_provider, "url": img["url"],
                            "local": f"data/stories/{story_id}/assets/{local_name}",
                            "caption": caption,
                            "keyword": q,
                        })
                        img_idx += 1
                        print(f"[assets]   ✓ 保存 {local_name} 说明={caption}", flush=True)
                    else:
                        print(f"[assets]   ✗ status={ir.status_code} size={len(ir.content)}", flush=True)
                except Exception as e:
                    print(f"[assets] 下载失败: {e}", flush=True)
                await asyncio.sleep(1)

        c = get_db()
        c.execute("UPDATE stories SET assets=? WHERE id=?",
                  (json.dumps(assets, ensure_ascii=False), story_id))
        c.commit(); c.close()
        print(f"[assets] story {story_id}: {len(assets)} assets fetched", flush=True)

    background_tasks.add_task(_run_fetch, story_id)
    return {"ok": True, "message": "素材抓取中，请稍后刷新"}

# ── 即梦AI 封面生成 ──────────────────────────────────────────────────────────
@app.post("/api/stories/{story_id}/generate-cover")
async def api_generate_cover(story_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, b.title AS book_title, b.author AS book_author FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?",
        (story_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")
    if row["status"] not in ("script_approved", "producing", "done", "published"):
        raise HTTPException(400, "需要先审核通过脚本")
    if not row["script"]:
        raise HTTPException(400, "脚本内容为空")

    async def do_cover():
        title  = row["book_title"] or ""
        author = row["book_author"] or ""
        try:
            loop = asyncio.get_event_loop()
            import functools
            img_bytes = await loop.run_in_executor(
                None, functools.partial(make_cover_image, title, author)
            )
            cover_dir = STORIES_DIR / str(story_id)
            cover_dir.mkdir(parents=True, exist_ok=True)
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:30]
            cover_path = cover_dir / f"{safe_title}_cover.jpg"
            cover_path.write_bytes(img_bytes)
            c = get_db()
            c.execute("UPDATE stories SET cover_path=? WHERE id=?", (str(cover_path), story_id))
            c.commit(); c.close()
            print(f"[cover] story {story_id}: 封面已保存 ({len(img_bytes)//1024}kB) → {cover_path}", flush=True)
        except Exception as e:
            print(f"[cover] 生成失败: {e}", flush=True)

    background_tasks.add_task(_run_cover, story_id)
    return {"ok": True, "message": "封面生成中，约3秒后刷新"}

# ── 配音生成（Volcengine TTS）───────────────────────────────────────────────
@app.post("/api/stories/{story_id}/generate-audio")
async def api_generate_audio(story_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    row = conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")
    if row["status"] not in ("script_approved", "producing", "done", "published"):
        raise HTTPException(400, "需要先审核通过脚本")
    script = row["script"] or ""
    if not script:
        raise HTTPException(400, "脚本内容为空")

    async def do_tts():
        # 清空 audio_path，UI 立刻隐藏旧音频播放器
        c = get_db(); c.execute("UPDATE stories SET audio_path=NULL WHERE id=?", (story_id,)); c.commit(); c.close()
        # 删除旧音频文件
        (STORIES_DIR / str(story_id) / "audio.mp3").unlink(missing_ok=True)

        app_id = cfg("VOLC_APPID")
        token = cfg("VOLC_TOKEN")
        resource_id = cfg("VOLC_RESOURCE_ID", "volc.megatts.voiceclone")
        voice_type = cfg("VOLC_VOICE_TYPE")
        print(f"[tts] 使用音色: {voice_type!r}  resource_id={resource_id}", flush=True)
        if not all([app_id, token, voice_type]):
            c = get_db()
            c.execute("UPDATE stories SET status='producing' WHERE id=?", (story_id,))
            c.commit(); c.close()
            print(f"[tts] Volcengine env vars not set, skipping TTS for story {story_id}", flush=True)
            return

        clean_script = re.sub(r"【[^】]*】", "", script).strip()

        # 在第一句话（引导语）后插入 1 秒停顿：拆成两段分别合成再拼接
        # 在"今天讲的是"之后插入停顿，使书名有呼吸感
        m_split = re.search(r'今天[要]?讲的是', clean_script)
        if m_split:
            part1 = clean_script[:m_split.end()].strip()
            part2 = clean_script[m_split.end():].strip()
        else:
            # 备选：第一个句子结束处
            first_end = re.search(r'[。！？]', clean_script)
            if first_end:
                part1 = clean_script[:first_end.end()].strip()
                part2 = clean_script[first_end.end():].strip()
            else:
                part1 = clean_script
                part2 = ""

        tts_cfg = load_tts_settings()
        print(f"[tts] 设置: 语速={tts_cfg['speed_ratio']} 音调={tts_cfg['pitch_ratio']} 音量={tts_cfg['volume_ratio']} 停顿={tts_cfg['silence_s']}s", flush=True)

        async def tts_call(text: str) -> bytes:
            payload = {
                "app": {"appid": app_id, "token": token, "cluster": "volcano_tts"},
                "user": {"uid": "bookstory"},
                "audio": {
                    "voice_type": voice_type,
                    "encoding": "mp3",
                    "speed_ratio": tts_cfg["speed_ratio"],
                    "volume_ratio": tts_cfg["volume_ratio"],
                    "pitch_ratio":  tts_cfg["pitch_ratio"],
                },
                "request": {
                    "reqid": str(uuid.uuid4()),
                    "text": text,
                    "text_type": "plain",
                    "operation": "query",
                },
            }
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://openspeech.bytedance.com/api/v1/tts",
                    headers={"Authorization": f"Bearer;{token}", "Resource-Id": resource_id},
                    json=payload,
                )
            if r.status_code != 200:
                raise Exception(f"TTS API错误: {r.status_code} {r.text[:200]}")
            data = r.json()
            if data.get("code") != 3000:
                raise Exception(f"TTS失败: {data.get('message', '未知错误')}")
            return base64.b64decode(data["data"])

        try:
            story_dir = STORIES_DIR / str(story_id)
            story_dir.mkdir(exist_ok=True)

            # 进一步拆分 part2：书名 + 正文（在书名后再加一个停顿）
            # 书名通常在 《》 内，找第一个 》的位置
            part_title = ""
            part_story = part2
            if part2:
                m_title = re.search(r'》', part2)
                if m_title:
                    part_title = part2[:m_title.end()].strip()
                    part_story  = part2[m_title.end():].strip()
                else:
                    # 备选：第一个句末标点
                    m_sent = re.search(r'[。！？]', part2)
                    if m_sent:
                        part_title = part2[:m_sent.end()].strip()
                        part_story  = part2[m_sent.end():].strip()

            bytes1 = await tts_call(part1)
            (story_dir / "tts_part1.mp3").write_bytes(bytes1)

            if part2:
                concat_list = story_dir / "tts_concat.txt"
                silence1 = story_dir / "tts_silence1.mp3"  # 今天讲的是 → 书名
                silence2 = story_dir / "tts_silence2.mp3"  # 书名 → 正文

                async def make_silence(path, duration: float):
                    await run_subprocess(
                        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                         "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", str(path)],
                        capture_output=True, timeout=15
                    )

                await make_silence(silence1, 0.3)  # 今天讲的是 → 书名

                audio_path = story_dir / "audio.mp3"

                if part_title and part_story:
                    # 三段：part1 + 0.3s + 书名 + 0.3s + 正文
                    await make_silence(silence2, 0.3)
                    bytes_title = await tts_call(part_title)
                    bytes_story = await tts_call(part_story)
                    (story_dir / "tts_title.mp3").write_bytes(bytes_title)
                    (story_dir / "tts_story.mp3").write_bytes(bytes_story)
                    concat_list.write_text(
                        f"file '{(story_dir / 'tts_part1.mp3').resolve()}'\n"
                        f"file '{silence1.resolve()}'\n"
                        f"file '{(story_dir / 'tts_title.mp3').resolve()}'\n"
                        f"file '{silence2.resolve()}'\n"
                        f"file '{(story_dir / 'tts_story.mp3').resolve()}'\n",
                        encoding="utf-8"
                    )
                    await run_subprocess(
                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                         "-i", str(concat_list), "-c", "copy", str(audio_path)],
                        capture_output=True, timeout=60
                    )
                    concat_list.unlink(missing_ok=True)
                    silence1.unlink(missing_ok=True)
                    silence2.unlink(missing_ok=True)
                    (story_dir / "tts_part1.mp3").unlink(missing_ok=True)
                    (story_dir / "tts_title.mp3").unlink(missing_ok=True)
                    (story_dir / "tts_story.mp3").unlink(missing_ok=True)
                else:
                    # 无法拆书名，退化为两段：part1 + 0.3s + part2
                    bytes2 = await tts_call(part2)
                    (story_dir / "tts_part2.mp3").write_bytes(bytes2)
                    concat_list.write_text(
                        f"file '{(story_dir / 'tts_part1.mp3').resolve()}'\n"
                        f"file '{silence1.resolve()}'\n"
                        f"file '{(story_dir / 'tts_part2.mp3').resolve()}'\n",
                        encoding="utf-8"
                    )
                    await run_subprocess(
                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                         "-i", str(concat_list), "-c", "copy", str(audio_path)],
                        capture_output=True, timeout=60
                    )
                    concat_list.unlink(missing_ok=True)
                    silence1.unlink(missing_ok=True)
                    (story_dir / "tts_part1.mp3").unlink(missing_ok=True)
                    (story_dir / "tts_part2.mp3").unlink(missing_ok=True)
            else:
                audio_path = story_dir / "audio.mp3"
                (story_dir / "tts_part1.mp3").rename(audio_path)

            c = get_db()
            c.execute(
                "UPDATE stories SET audio_path=?, status='producing', updated_at=? WHERE id=?",
                (str(audio_path), int(datetime.now().timestamp()), story_id)
            )
            c.commit(); c.close()
            print(f"[tts] story {story_id}: audio saved ({part1[:20]}… | 书名:{part_title[:10] if part_title else '-'} | 正文:{len(part_story)}字)", flush=True)
        except Exception as e:
            print(f"[tts] story {story_id} failed: {e}", flush=True)

    background_tasks.add_task(_run_tts, story_id)
    return {"ok": True, "message": "TTS配音任务已启动"}

# ── Remotion 项目模板文件 ──────────────────────────────────────────────────────
REMOTION_DIR = DATA_DIR / "book-story-video"

REMOTION_PACKAGE_JSON = """{
  "name": "book-story-video",
  "version": "1.0.0",
  "scripts": { "build": "remotion render" },
  "dependencies": {
    "remotion": "^4.0.0",
    "@remotion/captions": "^4.0.0",
    "@remotion/cli": "^4.0.0",
    "mediabunny": "latest",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/react": "^18.0.0"
  }
}
"""

REMOTION_CONFIG_TS = """import {Config} from '@remotion/cli/config';
Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
"""

REMOTION_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2018",
    "module": "commonjs",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "lib": ["es2015"],
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "noUnusedLocals": true
  },
  "exclude": ["remotion.config.ts"]
}
"""

REMOTION_GET_AUDIO_DURATION_TS = """import { Input, ALL_FORMATS, UrlSource } from "mediabunny";

export const getAudioDuration = async (src: string): Promise<number> => {
  const input = new Input({
    formats: ALL_FORMATS,
    source: new UrlSource(src, { getRetryDelay: () => null }),
  });
  return input.computeDuration();
};
"""

REMOTION_CAPTION_OVERLAY_TSX = """import { useCallback, useEffect, useMemo, useState } from "react";
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
"""

REMOTION_COMPOSITION_TSX = """import {
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
"""

REMOTION_ROOT_TSX = """import { Composition } from "remotion";
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
"""

REMOTION_INDEX_CSS = """body { margin: 0; font-family: sans-serif; }
"""

REMOTION_ENTRY_TS = """import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
"""


def write_remotion_project():
    """创建 Remotion 项目目录和模板文件（不执行 npm install）"""
    REMOTION_DIR.mkdir(parents=True, exist_ok=True)
    (REMOTION_DIR / "src").mkdir(exist_ok=True)
    (REMOTION_DIR / "public" / "images").mkdir(parents=True, exist_ok=True)
    (REMOTION_DIR / "public" / "voiceover").mkdir(parents=True, exist_ok=True)
    (REMOTION_DIR / "public" / "captions").mkdir(parents=True, exist_ok=True)
    files = {
        "package.json": REMOTION_PACKAGE_JSON,
        "remotion.config.ts": REMOTION_CONFIG_TS,
        "tsconfig.json": REMOTION_TSCONFIG,
        "src/get-audio-duration.ts": REMOTION_GET_AUDIO_DURATION_TS,
        "src/CaptionOverlay.tsx": REMOTION_CAPTION_OVERLAY_TSX,
        "src/Composition.tsx": REMOTION_COMPOSITION_TSX,
        "src/Root.tsx": REMOTION_ROOT_TSX,
        "src/index.css": REMOTION_INDEX_CSS,
        "src/index.ts": REMOTION_ENTRY_TS,
    }
    for rel, content in files.items():
        (REMOTION_DIR / rel).write_text(content, encoding="utf-8")
    print(f"[remotion] 项目文件已写入 {REMOTION_DIR}", flush=True)


@app.post("/api/setup-remotion")
async def api_setup_remotion(background_tasks: BackgroundTasks):
    async def do_setup():
        write_remotion_project()
        print("[remotion] 正在 npm install…", flush=True)
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(REMOTION_DIR),
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print("[remotion] ✓ npm install 完成", flush=True)
        else:
            print(f"[remotion] npm install 失败:\n{result.stderr[-500:]}", flush=True)

    background_tasks.add_task(do_setup)
    return {"ok": True, "message": "Remotion 项目初始化中（约1-2分钟）"}


async def tts_v3_scene(text: str, scene_id: str, voiceover_dir: Path, captions_dir: Path):
    """用 Volcengine TTS v3 异步 API 生成单场景音频+字幕（带词级时间戳）"""
    app_id = cfg("VOLC_APPID")
    access_key = cfg("VOLC_TOKEN")
    resource_id = cfg("VOLC_V3_RESOURCE_ID", "seed-tts-1.0")
    voice_type = cfg("VOLC_VOICE_TYPE")
    print(f"[tts_v3] scene={scene_id} 音色={voice_type!r} resource={resource_id}", flush=True)

    def make_headers():
        return {
            "Content-Type": "application/json",
            "X-Api-App-Id": app_id,
            "X-Api-Access-Key": access_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
        }

    submit_payload = {
        "user": {"uid": "bookstory"},
        "unique_id": str(uuid.uuid4()),
        "req_params": {
            "text": text,
            "speaker": voice_type,
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000,
                "enable_timestamp": True,
            },
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://openspeech.bytedance.com/api/v3/tts/submit",
            headers=make_headers(), json=submit_payload,
        )
    data = r.json()
    if data.get("code") != 20000000:
        raise Exception(f"TTS v3 submit失败: {data.get('message', data)}")
    task_id = data["data"]["task_id"]
    print(f"[tts_v3] {scene_id} submitted task_id={task_id}", flush=True)

    # 轮询结果
    for i in range(60):
        await asyncio.sleep(3)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://openspeech.bytedance.com/api/v3/tts/query",
                headers=make_headers(), json={"task_id": task_id},
            )
        data = r.json()
        if data.get("code") != 20000000:
            raise Exception(f"TTS v3 query失败: {data.get('message', data)}")
        status = data["data"]["task_status"]
        if status == 2:
            audio_url = data["data"]["audio_url"]
            sentences = data["data"].get("sentences", [])
            print(f"[tts_v3] ✓ {scene_id} done ({i*3+3}s)", flush=True)
            break
        elif status == 3:
            raise Exception(f"TTS v3任务失败: task_id={task_id}")
    else:
        raise Exception(f"TTS v3超时: {scene_id}")

    # 下载音频
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        ar = await client.get(audio_url)
    (voiceover_dir / f"{scene_id}.mp3").write_bytes(ar.content)

    # 生成字幕 JSON（词级时间戳）
    captions = []
    for sent in sentences:
        for word in sent.get("words", []):
            captions.append({
                "text": word["word"],
                "startMs": int(word["startTime"] * 1000),
                "endMs": int(word["endTime"] * 1000),
                "timestampMs": int(word["startTime"] * 1000),
                "confidence": word.get("confidence", 1.0),
            })
    (captions_dir / f"{scene_id}.json").write_text(
        json.dumps(captions, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[tts_v3] ✓ {scene_id}: {len(captions)} 词", flush=True)


# ── 视频合成（Remotion）──────────────────────────────────────────────────────
@app.post("/api/stories/{story_id}/render-video")
async def api_render_video(story_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, b.title, b.author FROM stories s JOIN books b ON s.book_id=b.id WHERE s.id=?",
        (story_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "故事不存在")

    async def do_render():
        story_dir = STORIES_DIR / str(story_id)
        story_dir.mkdir(exist_ok=True)
        title = row["title"]
        safe_title = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:30]
        output_path = story_dir / f"{safe_title}_video.mp4"
        author = row["author"] or ""
        script = row["script"] or ""

        def set_error(msg: str):
            c = get_db()
            c.execute("UPDATE stories SET error_msg=?, status='script_approved' WHERE id=?",
                      (msg, story_id))
            c.commit(); c.close()

        # 检查 Remotion 项目是否已初始化
        if not (REMOTION_DIR / "node_modules").exists():
            set_error("请先点击「初始化视频项目」")
            print(f"[render] Remotion 未初始化，请先调用 /api/setup-remotion", flush=True)
            return

        # 每次渲染前更新 Composition.tsx（确保使用最新效果）
        (REMOTION_DIR / "src" / "Composition.tsx").write_text(REMOTION_COMPOSITION_TSX, encoding="utf-8")

        # 拷贝片头组件到主工程 src/Intro.tsx
        import shutil as _shutil
        # 拷贝 FilmStrip.tsx，并将固定 FILM_DURATION 替换为动态 durationInFrames
        intro_src = Path("intro_src/FilmStrip.tsx")
        if intro_src.exists():
            intro_code = intro_src.read_text(encoding="utf-8")
            # 让动画时长跟随 Sequence 的实际帧数，实现与音频精准对齐
            intro_code = intro_code.replace(
                "const { width, height } = useVideoConfig();",
                "const { width, height, durationInFrames } = useVideoConfig();"
            )
            intro_code = intro_code.replace(
                "[0, FILM_DURATION]",
                "[0, durationInFrames]"
            )
            (REMOTION_DIR / "src" / "FilmStrip.tsx").write_text(intro_code, encoding="utf-8")
            # 拷贝片头图片资源到 Remotion public 目录
            pub_dir = REMOTION_DIR / "public"
            intro_pub = Path("intro_src/public")
            if intro_pub.exists():
                for img_file in intro_pub.iterdir():
                    _shutil.copy2(str(img_file), str(pub_dir / img_file.name))
            print(f"[render] 片头组件 FilmStrip.tsx 已拷贝，图片资源已同步", flush=True)
        else:
            print(f"[render] 警告：找不到 intro_src/FilmStrip.tsx，片头将跳过", flush=True)

        # 检查 TTS 配置
        if not all([cfg("VOLC_APPID"), cfg("VOLC_TOKEN"), cfg("VOLC_VOICE_TYPE")]):
            set_error("请先配置 VOLC_APPID / VOLC_TOKEN / VOLC_VOICE_TYPE")
            return

        # 收集素材图片（封面→作者→故事图），过滤分辨率过低的图片
        asset_dir = story_dir / "assets"
        all_img_files = sorted(asset_dir.glob("*.jpg")) if asset_dir.exists() else []
        img_files = []
        for _f in all_img_files:
            try:
                import io
                from PIL import Image as PILImage
                _img = PILImage.open(_f)
                _w, _h = _img.size
                if _w >= 300 and _h >= 300:
                    img_files.append(_f)
                else:
                    print(f"[render] 跳过低分辨率图片 {_f.name} ({_w}x{_h})", flush=True)
            except Exception:
                img_files.append(_f)  # 无法检测时保留
        if not img_files:
            set_error("请先抓取素材再生成视频")
            return

        # 脚本分段：先按【标记】或双换行，没有则按句子智能分组（每段约40-60字）
        raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n|(?=【)', script) if p.strip()]
        if len(raw_paragraphs) <= 1:
            # 一段连续文本：按句号/感叹号/问号切句，再合并成约40-60字的组
            sentences = re.split(r'(?<=[。！？])', script.strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            groups, buf = [], ""
            for s in sentences:
                if len(buf) + len(s) <= 60:
                    buf += s
                else:
                    if buf:
                        groups.append(buf)
                    buf = s
            if buf:
                groups.append(buf)
            raw_paragraphs = groups if groups else [script]
        # 去掉开头的【xxx】标注（兼容旧格式）
        paragraphs = [re.sub(r'^【[^】]*】\s*', '', p).strip() for p in raw_paragraphs]
        paragraphs = [p for p in paragraphs if p]
        print(f"[render] story {story_id}: {len(paragraphs)} 个场景，{len(img_files)} 张图", flush=True)

        # 检查已生成的配音
        audio_src = story_dir / "audio.mp3"
        if not audio_src.exists():
            set_error("请先生成配音再合成视频")
            return

        # 清空 video_path，UI 立刻隐藏旧视频下载/预览按钮
        c = get_db(); c.execute("UPDATE stories SET video_path=NULL WHERE id=?", (story_id,)); c.commit(); c.close()
        # 删除旧视频文件（兼容旧文件名 video.mp4 和新格式 *_video.mp4）
        for _old in list(story_dir.glob("*_video.mp4")) + [story_dir / "video.mp4"]:
            _old.unlink(missing_ok=True)

        # 准备 Remotion public 目录
        pub_images = REMOTION_DIR / "public" / "images"
        pub_images.mkdir(parents=True, exist_ok=True)
        # 清理旧的 scene-XX 文件
        for f in pub_images.glob("scene-*"):
            f.unlink(missing_ok=True)

        # 复制整段音频
        import shutil
        pub_audio = REMOTION_DIR / "public" / "audio.mp3"
        shutil.copy2(str(audio_src), str(pub_audio))

        # ffprobe 获取总时长
        probe = await run_subprocess(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(pub_audio)],
            capture_output=True, text=True,
        )
        total_duration_s = 30.0
        try:
            total_duration_s = float(json.loads(probe.stdout)["format"]["duration"])
        except Exception:
            pass
        FPS = 30

        # ── 计算片头帧数：音频里说完"今天讲的是"之前的时长 ─────────────────
        n_scenes = len(img_files)
        audio_frames = math.ceil(total_duration_s * FPS) + 20

        # 在脚本中找"今天讲的是"的位置，按字符比例估算时间点
        m_intro = re.search(r'今天讲的是', script)
        intro_end_pos = m_intro.end() if m_intro else 0
        if not intro_end_pos and title:
            # 找书名首次出现位置作为备选
            intro_end_pos = script.find(title[:4]) if len(title) >= 4 else script.find(title)
            intro_end_pos = max(0, intro_end_pos)
        total_script_chars = len(script)
        if total_script_chars > 0 and intro_end_pos > 0:
            intro_frames = int((intro_end_pos / total_script_chars) * audio_frames)
        else:
            intro_frames = 90  # 默认 3 秒
        intro_frames = max(60, min(intro_frames, 150))  # 限制在 2s ~ 5s（至少留够转场帧数）
        intro_frames += 12  # +0.4s 让胶卷滚动更慢
        # 如果找不到片头文件，不插片头
        if not (REMOTION_DIR / "src" / "FilmStrip.tsx").exists():
            intro_frames = 0
        print(f"[render] 片头帧数={intro_frames}（{intro_frames/FPS:.1f}s），内容图片从此后开始", flush=True)

        # ── 场景：N 张图分配片头之后的剩余帧 ──────────────────────────────
        content_frames = audio_frames - intro_frames
        base = content_frames // n_scenes
        scene_frames = [base] * n_scenes
        for i in range(content_frames - sum(scene_frames)):  # 分配余数帧
            scene_frames[i] += 1
        total_frames = intro_frames + sum(scene_frames)

        scene_images = []
        for i, img in enumerate(img_files):
            dest = pub_images / f"scene-{i+1:02d}{img.suffix}"
            shutil.copy2(str(img), str(dest))
            scene_images.append(f"images/scene-{i+1:02d}{img.suffix}")
        print(f"[render] 总时长={total_duration_s:.1f}s 总帧数={total_frames} 图片数={n_scenes}", flush=True)

        # 复制 CoverTransition.tsx
        cover_trans_src = Path("intro_src/CoverTransition.tsx")
        if cover_trans_src.exists():
            _shutil.copy2(str(cover_trans_src), str(REMOTION_DIR / "src" / "CoverTransition.tsx"))

        # 找书封图片并复制到 public/story_cover.jpg
        story_cover_file = ""
        if img_files:
            _shutil.copy2(str(img_files[0]), str(REMOTION_DIR / "public" / "story_cover.jpg"))
            story_cover_file = "story_cover.jpg"
            print(f"[render] 书封已复制: {img_files[0].name}", flush=True)

        # ── 字幕：句子再拆成 ≤18 字小段，字符比例分配时间 ────────────────────
        def to_subtitle_chunks(text: str, max_len: int = 18) -> list[str]:
            sentences = [s.strip() for s in re.split(r'(?<=[。！？])', text.strip()) if s.strip()]
            chunks = []
            for sent in sentences:
                while len(sent) > max_len:
                    split_at = None
                    for j in range(min(max_len, len(sent) - 1), 0, -1):
                        if sent[j] in '，、；：':
                            split_at = j + 1
                            break
                    if split_at is None:
                        split_at = max_len
                    chunks.append(sent[:split_at])
                    sent = sent[split_at:]
                if sent:
                    chunks.append(sent)
            return [c.rstrip('。！？，、；：…—') for c in chunks]

        total_ms = int(total_duration_s * 1000)
        sub_chunks = to_subtitle_chunks(script.strip())
        total_chunk_chars = sum(len(c) for c in sub_chunks)
        subtitles = []
        cur_ms = 0
        for chunk in sub_chunks:
            dur_ms = int(total_ms * len(chunk) / total_chunk_chars) if total_chunk_chars else 2000
            subtitles.append({"text": chunk, "startMs": cur_ms, "endMs": cur_ms + dur_ms})
            cur_ms += dur_ms
        # 书名大字：从内容图片开始那一帧出现，持续 2.5 秒
        title_card_start_ms = int(intro_frames / FPS * 1000)
        title_card_end_ms   = title_card_start_ms + 2500

        # 生成 content.ts
        scene_entries = []
        for i in range(n_scenes):
            scene_entries.append(
                f'  {{ id: "scene-{i+1:02d}", image: "{scene_images[i]}", '
                f'narration: "", durationInFrames: {scene_frames[i]} }}'
            )
        subtitle_entries = ",\n".join(
            f'  {{ text: {json.dumps(s["text"], ensure_ascii=False)}, startMs: {s["startMs"]}, endMs: {s["endMs"]} }}'
            for s in subtitles
        )
        content_ts = (
            'export type Scene = { id: string; image: string; narration: string; durationInFrames: number };\n'
            'export type Sub = { text: string; startMs: number; endMs: number };\n\n'
            'export const SCENES: Scene[] = [\n' + ',\n'.join(scene_entries) + '\n];\n\n'
            'export const SUBTITLES: Sub[] = [\n' + subtitle_entries + '\n];\n\n'
            f'export const TOTAL_FRAMES = {total_frames};\n'
            'export const AUDIO_FILE = "audio.mp3";\n'
            f'export const BOOK_TITLE = {json.dumps(title, ensure_ascii=False)};\n'
            f'export const TITLE_CARD_MS = {{ startMs: {title_card_start_ms}, endMs: {title_card_end_ms} }};\n'
            f'export const INTRO_FRAMES = {intro_frames};\n'
            f'export const STORY_COVER = {json.dumps(story_cover_file)};\n'
        )
        (REMOTION_DIR / "src" / "content.ts").write_text(content_ts, encoding="utf-8")
        print(f"[render] content.ts 已生成，字幕{len(subtitles)}句", flush=True)

        # 执行 Remotion render
        output_path.parent.mkdir(parents=True, exist_ok=True)
        render_cmd = [
            "npx", "remotion", "render",
            "src/index.ts",
            "BookStory",
            str(output_path.resolve()),
        ]
        print(f"[render] 开始 Remotion 渲染…", flush=True)
        result = await run_subprocess(
            render_cmd, cwd=str(REMOTION_DIR),
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0 and output_path.exists():
            # 重新编码：修复色彩空间 + faststart，确保浏览器正常播放
            web_path = story_dir / "video_web.mp4"
            fs = await run_subprocess(
                ["ffmpeg", "-y", "-i", str(output_path),
                 "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                 "-pix_fmt", "yuv420p",
                 "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                 "-c:a", "aac", "-b:a", "128k",
                 "-movflags", "+faststart",
                 str(web_path)],
                capture_output=True, timeout=180
            )
            if fs.returncode == 0 and web_path.exists():
                web_path.replace(output_path)
                print(f"[render] ✓ 视频 web 优化完成", flush=True)

            c = get_db()
            c.execute("UPDATE stories SET video_path=?, status='done' WHERE id=?",
                      (str(output_path), story_id))
            c.commit(); c.close()
            print(f"[render] ✓ story {story_id}: 视频已保存 {output_path}", flush=True)
        else:
            err = (result.stderr or result.stdout or "未知错误")
            print(f"[render] Remotion 失败 (stdout):\n{result.stdout[-1000:]}", flush=True)
            print(f"[render] Remotion 失败 (stderr):\n{result.stderr[-1000:]}", flush=True)
            set_error(f"渲染失败: {err[-100:]}")

    async def do_render_safe():
        try:
            await do_render()
        except Exception as e:
            import traceback
            print(f"[render] 未捕获异常: {e}\n{traceback.format_exc()}", flush=True)
            try:
                set_error(f"渲染异常: {str(e)[:100]}")
            except Exception:
                pass

    background_tasks.add_task(_run_render, story_id)
    return {"ok": True, "message": "视频合成任务已启动"}

# ══════════════════════════════════════════════════════════════════════════════
# 一键全流程：模块级后台任务函数（可被 pipeline 直接调用）
# ══════════════════════════════════════════════════════════════════════════════

async def _run_generate(story_id: int):
    """生成脚本（模块级，供 pipeline 调用）。"""
    row = db_get_story(story_id)
    if not row:
        print(f"[script] story {story_id} not found", flush=True)
        return
    print(f"[script] ▶ 开始 story={story_id} 《{row['book_title']}》角度={row['angle']}", flush=True)
    c = get_db()
    c.execute("UPDATE stories SET status='scripting' WHERE id=?", (story_id,))
    c.commit(); c.close()

    summary_raw = row["research_summary"] or "{}"
    try:
        summary = json.loads(summary_raw)
    except Exception:
        summary = {}
    facts = summary.get("facts", [])
    research_text = summary.get("summary", "") + "\n\n关键事实：\n" + "\n".join(f"- {f}" for f in facts)

    prompt = SCRIPT_TEMPLATE.format(
        title=row["book_title"], author=row["book_author"] or "未知",
        angle=row["angle"],
        angle_focus=SCRIPT_PROMPTS.get(row["angle"], row["angle"]),
        research=research_text,
    )
    script = await kimi_chat(prompt, temperature=1)
    script = add_script_intro(script, row["book_title"])

    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "script_draft.txt").write_text(script, encoding="utf-8")

    c = get_db()
    c.execute("UPDATE stories SET script=?, status='script_draft' WHERE id=?", (script, story_id))
    c.commit(); c.close()
    print(f"[script] story {story_id} done", flush=True)


async def _run_fetch(story_id: int):
    """抓取素材（模块级，供 pipeline 调用）。"""
    row = db_get_story(story_id)
    if not row:
        print(f"[assets] story {story_id} not found", flush=True)
        return
    asset_dir = STORIES_DIR / str(story_id) / "assets"
    c = get_db(); c.execute("UPDATE stories SET assets='[]' WHERE id=?", (story_id,)); c.commit(); c.close()
    import shutil as _shutil
    _shutil.rmtree(str(asset_dir), ignore_errors=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    title = row["book_title"]
    author = row["book_author"] or ""
    script = row["script"] or ""
    angle = row["angle"] or ""

    DOUBAN_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://book.douban.com/",
    }
    cover_url = row["book_cover"]
    if not cover_url and title:
        try:
            async with httpx.AsyncClient(timeout=10, headers=DOUBAN_HEADERS) as client:
                r = await client.get(
                    "https://book.douban.com/j/subject_suggest",
                    params={"q": title},
                )
            if r.status_code == 200:
                items = r.json()
                best = None
                for item in items:
                    if item.get("type") != "b":
                        continue
                    if item.get("title", "").startswith(title):
                        best = item
                        break
                if not best and items:
                    best = next((i for i in items if i.get("type") == "b"), None)
                if best and best.get("pic"):
                    cover_url = best["pic"].replace("/s/public/", "/l/public/")
                    print(f"[assets] 豆瓣封面: {cover_url}", flush=True)
        except Exception as e:
            print(f"[assets] 豆瓣查询失败: {e}", flush=True)

    if cover_url:
        try:
            async with httpx.AsyncClient(timeout=15, headers=DOUBAN_HEADERS,
                                         follow_redirects=True) as client:
                r = await client.get(cover_url)
            cover_too_small = False
            if r.status_code == 200 and len(r.content) > 2000:
                try:
                    import io
                    from PIL import Image as PILImage
                    img_check = PILImage.open(io.BytesIO(r.content))
                    w, h = img_check.size
                    if w < 400 or h < 400:
                        print(f"[assets] 豆瓣封面过小 {w}x{h}，尝试更好来源", flush=True)
                        cover_too_small = True
                    else:
                        print(f"[assets] 豆瓣封面尺寸 {w}x{h}，可用", flush=True)
                except Exception:
                    pass
            if r.status_code == 200 and len(r.content) > 2000 and not cover_too_small:
                cover_bytes = r.content
                cover_final_url = cover_url
            else:
                cover_bytes = None
                cover_final_url = cover_url
        except Exception as e:
            cover_bytes = None
            cover_final_url = cover_url
            print(f"[assets] 豆瓣封面下载失败: {e}", flush=True)

        if not cover_bytes and title:
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    ol = await client.get(
                        "https://openlibrary.org/search.json",
                        params={"title": title, "author": author or "", "limit": 3},
                    )
                for doc in (ol.json() if ol.text.strip() else {}).get("docs", []):
                    cid = doc.get("cover_i")
                    if not cid:
                        continue
                    ol_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"
                    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                        ol_r = await client.get(ol_url)
                    if ol_r.status_code == 200 and len(ol_r.content) > 10000:
                        cover_bytes = ol_r.content
                        cover_final_url = ol_url
                        print(f"[assets] Open Library封面: {ol_url}", flush=True)
                        break
            except Exception as e:
                print(f"[assets] Open Library封面失败: {e}", flush=True)

        if not cover_bytes and title:
            try:
                def title_bigrams(t: str) -> list:
                    t2 = re.sub(r'[\s·\-：:《》「」\'"]+', '', t)
                    return [t2[i:i+2] for i in range(len(t2) - 1)] if len(t2) >= 2 else [t2]
                kw_bigrams = title_bigrams(title)
                author_kws = [w.lower() for w in author.split() if len(w) >= 3] if author else []
                for brave_query in [
                    f'"{title}" 封面',
                    f'"{title}" book cover',
                    f'{title} {author} book cover'.strip(),
                ]:
                    brave_results = await brave_search_images(brave_query, limit=6)
                    for br in brave_results:
                        br_combined = (br.get("title", "") + " " + br.get("url", "")).lower()
                        matched = (
                            any(bg in br_combined for bg in kw_bigrams)
                            or any(ak in br_combined for ak in author_kws)
                        )
                        if not matched:
                            print(f"[assets] Brave封面不相关，跳过: {br.get('title','')[:60]}", flush=True)
                            continue
                        try:
                            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                                br_r = await client.get(br["url"])
                            if br_r.status_code == 200 and len(br_r.content) > 20000:
                                import io
                                from PIL import Image as PILImage
                                img_check = PILImage.open(io.BytesIO(br_r.content))
                                w, h = img_check.size
                                if w >= 200 and h >= 200:
                                    cover_bytes = br_r.content
                                    cover_final_url = br["url"]
                                    print(f"[assets] Brave封面: {br['url']} {w}x{h}", flush=True)
                                    break
                        except Exception:
                            continue
                    if cover_bytes:
                        break
            except Exception as e:
                print(f"[assets] Brave封面失败: {e}", flush=True)

        if cover_bytes:
            cover_path = asset_dir / "00_cover.jpg"
            cover_path.write_bytes(cover_bytes)
            assets.append({"type": "cover", "url": cover_final_url,
                           "local": f"data/stories/{story_id}/assets/00_cover.jpg",
                           "caption": f"《{title}》封面",
                           "keyword": "书封面"})
            print(f"[assets] ✓ 封面已保存 ({len(cover_bytes)//1024}KB)", flush=True)
        else:
            print(f"[assets] 封面获取失败", flush=True)

    if author:
        for author_q in [f"{author} portrait", f"{author} photograph", author]:
            imgs = await wikimedia_search_images(author_q, limit=3)
            if imgs:
                print(f"[assets] 作者图搜「{author_q}」→ {len(imgs)}张", flush=True)
                img = imgs[0]
                try:
                    async with httpx.AsyncClient(timeout=30, headers=WIKIMEDIA_HEADERS,
                                                 follow_redirects=True) as client:
                        ir = await client.get(img["url"])
                    if ir.status_code == 200 and len(ir.content) > 5000:
                        safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', author)[:20]
                        local_name = f"01_author_{safe}.jpg"
                        (asset_dir / local_name).write_bytes(ir.content)
                        caption = img.get("title", "").replace("File:", "").split(".")[0] or f"{author}照片"
                        assets.append({"type": "author", "url": img["url"],
                                       "local": f"data/stories/{story_id}/assets/{local_name}",
                                       "caption": caption, "keyword": f"{author}照片"})
                        print(f"[assets] ✓ 作者图已保存 {local_name}", flush=True)
                        break
                except Exception as e:
                    print(f"[assets] 作者图下载失败: {e}", flush=True)
                await asyncio.sleep(2)

    img_provider = cfg("IMAGE_SEARCH_PROVIDER", "wikimedia").lower()
    search_queries = [author]
    if script:
        try:
            if img_provider == "google":
                kw_hint = "适合在 Google 图片搜索的关键词，可以是具体场景、年代、地点、人物，也可以是能体现故事氛围的意象词。"
            else:
                kw_hint = "适合在 Wikimedia Commons 搜索的历史档案图片关键词，聚焦脚本中提到的具体人物、地点、事件、时代背景。"
            kw_prompt = f"""根据以下书籍故事脚本，提取3-5个{kw_hint}
要求：英文或中文关键词，不要用书名本身，要用脚本里的具体内容。

书名：《{title}》 作者：{author} 故事角度：{angle}
脚本：{script[:800]}

严格返回JSON：{{"keywords": ["关键词1", "关键词2", "关键词3"]}}"""
            kw_text = await kimi_chat(kw_prompt)
            kw_result = parse_json_response(kw_text)
            kw_list = kw_result.get("keywords", [])
            if kw_list:
                search_queries = kw_list[:4]
                print(f"[assets] Kimi搜图关键词({img_provider}): {search_queries}", flush=True)
        except Exception as e:
            print(f"[assets] 关键词提取失败，用默认: {e}", flush=True)

    img_idx = 1
    for q in search_queries:
        if not q or img_idx > 5:
            break
        images = await search_images(q, limit=3)
        print(f"[assets] [{img_provider}] 搜「{q}」→ {len(images)} 张", flush=True)
        for img in images[:2]:
            if img_idx > 5:
                break
            try:
                async with httpx.AsyncClient(timeout=30, headers=WIKIMEDIA_HEADERS,
                                             follow_redirects=True) as client:
                    ir = await client.get(img["url"])
                print(f"[assets]   {img['url'][-50:]} → {ir.status_code}", flush=True)
                if ir.status_code == 200 and len(ir.content) > 5000:
                    # 尺寸/比例检查：避免保存极窄/极矮的图（如图表、横幅）
                    try:
                        import io as _io
                        from PIL import Image as _PILImg
                        _dim = _PILImg.open(_io.BytesIO(ir.content)).size
                        _w, _h = _dim
                        _ratio = max(_w, _h) / max(min(_w, _h), 1)
                        if _w < 300 or _h < 300 or _ratio > 3.5:
                            print(f"[assets]   ✗ 跳过不适合视频的图 {_w}x{_h} ratio={_ratio:.1f}", flush=True)
                            continue
                    except Exception:
                        pass
                    safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', q)[:30]
                    local_name = f"{img_idx:02d}_{safe_name}.jpg"
                    (asset_dir / local_name).write_bytes(ir.content)
                    caption = img.get("title", "").replace("File:", "").split(".")[0] or q
                    assets.append({
                        "type": img_provider, "url": img["url"],
                        "local": f"data/stories/{story_id}/assets/{local_name}",
                        "caption": caption,
                        "keyword": q,
                    })
                    img_idx += 1
                    print(f"[assets]   ✓ 保存 {local_name} 说明={caption}", flush=True)
                else:
                    print(f"[assets]   ✗ status={ir.status_code} size={len(ir.content)}", flush=True)
            except Exception as e:
                print(f"[assets] 下载失败: {e}", flush=True)
            await asyncio.sleep(1)

    c = get_db()
    c.execute("UPDATE stories SET assets=? WHERE id=?",
              (json.dumps(assets, ensure_ascii=False), story_id))
    c.commit(); c.close()
    print(f"[assets] story {story_id}: {len(assets)} assets fetched", flush=True)


async def _run_cover(story_id: int):
    """生成封面（模块级，供 pipeline 调用）。"""
    row = db_get_story(story_id)
    if not row:
        print(f"[cover] story {story_id} not found", flush=True)
        return
    title  = row["book_title"] or ""
    author = row["book_author"] or ""
    try:
        loop = asyncio.get_event_loop()
        import functools
        img_bytes = await loop.run_in_executor(
            None, functools.partial(make_cover_image, title, author)
        )
        cover_dir = STORIES_DIR / str(story_id)
        cover_dir.mkdir(parents=True, exist_ok=True)
        safe_title = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:30]
        cover_path = cover_dir / f"{safe_title}_cover.jpg"
        cover_path.write_bytes(img_bytes)
        c = get_db()
        c.execute("UPDATE stories SET cover_path=? WHERE id=?", (str(cover_path), story_id))
        c.commit(); c.close()
        print(f"[cover] story {story_id}: 封面已保存 ({len(img_bytes)//1024}kB) → {cover_path}", flush=True)
    except Exception as e:
        print(f"[cover] 生成失败: {e}", flush=True)


async def _run_tts(story_id: int):
    """生成配音（模块级，供 pipeline 调用）。"""
    row = db_get_story(story_id)
    if not row:
        print(f"[tts] story {story_id} not found", flush=True)
        return
    script = row["script"] or ""
    if not script:
        print(f"[tts] story {story_id}: 脚本为空，跳过", flush=True)
        return

    c = get_db(); c.execute("UPDATE stories SET audio_path=NULL WHERE id=?", (story_id,)); c.commit(); c.close()
    (STORIES_DIR / str(story_id) / "audio.mp3").unlink(missing_ok=True)

    app_id = cfg("VOLC_APPID")
    token = cfg("VOLC_TOKEN")
    resource_id = cfg("VOLC_RESOURCE_ID", "volc.megatts.voiceclone")
    voice_type = cfg("VOLC_VOICE_TYPE")
    print(f"[tts] 使用音色: {voice_type!r}  resource_id={resource_id}", flush=True)
    if not all([app_id, token, voice_type]):
        c = get_db()
        c.execute("UPDATE stories SET status='producing' WHERE id=?", (story_id,))
        c.commit(); c.close()
        print(f"[tts] Volcengine env vars not set, skipping TTS for story {story_id}", flush=True)
        return

    clean_script = re.sub(r"【[^】]*】", "", script).strip()
    m_split = re.search(r'今天[要]?讲的是', clean_script)
    if m_split:
        part1 = clean_script[:m_split.end()].strip()
        part2 = clean_script[m_split.end():].strip()
    else:
        first_end = re.search(r'[。！？]', clean_script)
        if first_end:
            part1 = clean_script[:first_end.end()].strip()
            part2 = clean_script[first_end.end():].strip()
        else:
            part1 = clean_script
            part2 = ""

    tts_cfg = load_tts_settings()
    print(f"[tts] 设置: 语速={tts_cfg['speed_ratio']} 音调={tts_cfg['pitch_ratio']} 音量={tts_cfg['volume_ratio']} 停顿={tts_cfg['silence_s']}s", flush=True)

    async def tts_call(text: str) -> bytes:
        payload = {
            "app": {"appid": app_id, "token": token, "cluster": "volcano_tts"},
            "user": {"uid": "bookstory"},
            "audio": {
                "voice_type": voice_type,
                "encoding": "mp3",
                "speed_ratio": tts_cfg["speed_ratio"],
                "volume_ratio": tts_cfg["volume_ratio"],
                "pitch_ratio":  tts_cfg["pitch_ratio"],
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
            },
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                headers={"Authorization": f"Bearer;{token}", "Resource-Id": resource_id},
                json=payload,
            )
        if r.status_code != 200:
            raise Exception(f"TTS API错误: {r.status_code} {r.text[:200]}")
        data = r.json()
        if data.get("code") != 3000:
            raise Exception(f"TTS失败: {data.get('message', '未知错误')}")
        return base64.b64decode(data["data"])

    try:
        story_dir = STORIES_DIR / str(story_id)
        story_dir.mkdir(exist_ok=True)

        part_title = ""
        part_story = part2
        if part2:
            m_title = re.search(r'》', part2)
            if m_title:
                part_title = part2[:m_title.end()].strip()
                part_story  = part2[m_title.end():].strip()
            else:
                m_sent = re.search(r'[。！？]', part2)
                if m_sent:
                    part_title = part2[:m_sent.end()].strip()
                    part_story  = part2[m_sent.end():].strip()

        bytes1 = await tts_call(part1)
        (story_dir / "tts_part1.mp3").write_bytes(bytes1)

        if part2:
            concat_list = story_dir / "tts_concat.txt"
            silence1 = story_dir / "tts_silence1.mp3"
            silence2 = story_dir / "tts_silence2.mp3"

            async def make_silence(path, duration: float):
                await run_subprocess(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                     "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", str(path)],
                    capture_output=True, timeout=15
                )

            await make_silence(silence1, 0.3)
            audio_path = story_dir / "audio.mp3"

            if part_title and part_story:
                await make_silence(silence2, 0.3)
                bytes_title = await tts_call(part_title)
                bytes_story = await tts_call(part_story)
                (story_dir / "tts_title.mp3").write_bytes(bytes_title)
                (story_dir / "tts_story.mp3").write_bytes(bytes_story)
                concat_list.write_text(
                    f"file '{(story_dir / 'tts_part1.mp3').resolve()}'\n"
                    f"file '{silence1.resolve()}'\n"
                    f"file '{(story_dir / 'tts_title.mp3').resolve()}'\n"
                    f"file '{silence2.resolve()}'\n"
                    f"file '{(story_dir / 'tts_story.mp3').resolve()}'\n",
                    encoding="utf-8"
                )
                await run_subprocess(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_list), "-c", "copy", str(audio_path)],
                    capture_output=True, timeout=60
                )
                concat_list.unlink(missing_ok=True)
                silence1.unlink(missing_ok=True)
                silence2.unlink(missing_ok=True)
                (story_dir / "tts_part1.mp3").unlink(missing_ok=True)
                (story_dir / "tts_title.mp3").unlink(missing_ok=True)
                (story_dir / "tts_story.mp3").unlink(missing_ok=True)
            else:
                bytes2 = await tts_call(part2)
                (story_dir / "tts_part2.mp3").write_bytes(bytes2)
                concat_list.write_text(
                    f"file '{(story_dir / 'tts_part1.mp3').resolve()}'\n"
                    f"file '{silence1.resolve()}'\n"
                    f"file '{(story_dir / 'tts_part2.mp3').resolve()}'\n",
                    encoding="utf-8"
                )
                await run_subprocess(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_list), "-c", "copy", str(audio_path)],
                    capture_output=True, timeout=60
                )
                concat_list.unlink(missing_ok=True)
                silence1.unlink(missing_ok=True)
                (story_dir / "tts_part1.mp3").unlink(missing_ok=True)
                (story_dir / "tts_part2.mp3").unlink(missing_ok=True)
        else:
            audio_path = story_dir / "audio.mp3"
            (story_dir / "tts_part1.mp3").rename(audio_path)

        c = get_db()
        c.execute(
            "UPDATE stories SET audio_path=?, status='producing', updated_at=? WHERE id=?",
            (str(audio_path), int(datetime.now().timestamp()), story_id)
        )
        c.commit(); c.close()
        print(f"[tts] story {story_id}: audio saved ({part1[:20]}… | 书名:{part_title[:10] if part_title else '-'} | 正文:{len(part_story)}字)", flush=True)
    except Exception as e:
        print(f"[tts] story {story_id} failed: {e}", flush=True)


async def _run_render(story_id: int):
    """合成视频（模块级，供 pipeline 调用）。"""
    row = db_get_story(story_id)
    if not row:
        print(f"[render] story {story_id} not found", flush=True)
        return
    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    title = row["book_title"]
    safe_title = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:30]
    output_path = story_dir / f"{safe_title}_video.mp4"
    author = row["book_author"] or ""
    script = row["script"] or ""

    def set_error(msg: str):
        c = get_db()
        c.execute("UPDATE stories SET error_msg=?, status='script_approved' WHERE id=?",
                  (msg, story_id))
        c.commit(); c.close()

    try:
        if not (REMOTION_DIR / "node_modules").exists():
            set_error("请先点击「初始化视频项目」")
            print(f"[render] Remotion 未初始化，请先调用 /api/setup-remotion", flush=True)
            return

        (REMOTION_DIR / "src" / "Composition.tsx").write_text(REMOTION_COMPOSITION_TSX, encoding="utf-8")

        import shutil as _shutil
        intro_src = Path("intro_src/FilmStrip.tsx")
        if intro_src.exists():
            intro_code = intro_src.read_text(encoding="utf-8")
            intro_code = intro_code.replace(
                "const { width, height } = useVideoConfig();",
                "const { width, height, durationInFrames } = useVideoConfig();"
            )
            intro_code = intro_code.replace(
                "[0, FILM_DURATION]",
                "[0, durationInFrames]"
            )
            (REMOTION_DIR / "src" / "FilmStrip.tsx").write_text(intro_code, encoding="utf-8")
            pub_dir = REMOTION_DIR / "public"
            intro_pub = Path("intro_src/public")
            if intro_pub.exists():
                for img_file in intro_pub.iterdir():
                    _shutil.copy2(str(img_file), str(pub_dir / img_file.name))
            print(f"[render] 片头组件 FilmStrip.tsx 已拷贝，图片资源已同步", flush=True)
        else:
            print(f"[render] 警告：找不到 intro_src/FilmStrip.tsx，片头将跳过", flush=True)

        if not all([cfg("VOLC_APPID"), cfg("VOLC_TOKEN"), cfg("VOLC_VOICE_TYPE")]):
            set_error("请先配置 VOLC_APPID / VOLC_TOKEN / VOLC_VOICE_TYPE")
            return

        asset_dir = story_dir / "assets"
        all_img_files = sorted(asset_dir.glob("*.jpg")) if asset_dir.exists() else []
        img_files = []
        for _f in all_img_files:
            try:
                import io
                from PIL import Image as PILImage
                _img = PILImage.open(_f)
                _w, _h = _img.size
                if _w >= 300 and _h >= 300:
                    img_files.append(_f)
                else:
                    print(f"[render] 跳过低分辨率图片 {_f.name} ({_w}x{_h})", flush=True)
            except Exception:
                img_files.append(_f)
        if not img_files:
            set_error("请先抓取素材再生成视频")
            return

        raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n|(?=【)', script) if p.strip()]
        if len(raw_paragraphs) <= 1:
            sentences = re.split(r'(?<=[。！？])', script.strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            groups, buf = [], ""
            for s in sentences:
                if len(buf) + len(s) <= 60:
                    buf += s
                else:
                    if buf:
                        groups.append(buf)
                    buf = s
            if buf:
                groups.append(buf)
            raw_paragraphs = groups if groups else [script]
        paragraphs = [re.sub(r'^【[^】]*】\s*', '', p).strip() for p in raw_paragraphs]
        paragraphs = [p for p in paragraphs if p]
        print(f"[render] story {story_id}: {len(paragraphs)} 个场景，{len(img_files)} 张图", flush=True)

        audio_src = story_dir / "audio.mp3"
        if not audio_src.exists():
            set_error("请先生成配音再合成视频")
            return

        c = get_db(); c.execute("UPDATE stories SET video_path=NULL WHERE id=?", (story_id,)); c.commit(); c.close()
        for _old in list(story_dir.glob("*_video.mp4")) + [story_dir / "video.mp4"]:
            _old.unlink(missing_ok=True)

        pub_images = REMOTION_DIR / "public" / "images"
        pub_images.mkdir(parents=True, exist_ok=True)
        for f in pub_images.glob("scene-*"):
            f.unlink(missing_ok=True)

        import shutil
        pub_audio = REMOTION_DIR / "public" / "audio.mp3"
        shutil.copy2(str(audio_src), str(pub_audio))

        probe = await run_subprocess(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(pub_audio)],
            capture_output=True, text=True,
        )
        total_duration_s = 30.0
        try:
            total_duration_s = float(json.loads(probe.stdout)["format"]["duration"])
        except Exception:
            pass
        FPS = 30

        n_scenes = len(img_files)
        audio_frames = math.ceil(total_duration_s * FPS) + 20

        m_intro = re.search(r'今天讲的是', script)
        intro_end_pos = m_intro.end() if m_intro else 0
        if not intro_end_pos and title:
            intro_end_pos = script.find(title[:4]) if len(title) >= 4 else script.find(title)
            intro_end_pos = max(0, intro_end_pos)
        total_script_chars = len(script)
        if total_script_chars > 0 and intro_end_pos > 0:
            intro_frames = int((intro_end_pos / total_script_chars) * audio_frames)
        else:
            intro_frames = 90
        intro_frames = max(60, min(intro_frames, 150))
        intro_frames += 12
        if not (REMOTION_DIR / "src" / "FilmStrip.tsx").exists():
            intro_frames = 0
        print(f"[render] 片头帧数={intro_frames}（{intro_frames/FPS:.1f}s），内容图片从此后开始", flush=True)

        content_frames = audio_frames - intro_frames
        base = content_frames // n_scenes
        scene_frames = [base] * n_scenes
        for i in range(content_frames - sum(scene_frames)):
            scene_frames[i] += 1
        total_frames = intro_frames + sum(scene_frames)

        scene_images = []
        for i, img in enumerate(img_files):
            dest = pub_images / f"scene-{i+1:02d}{img.suffix}"
            shutil.copy2(str(img), str(dest))
            scene_images.append(f"images/scene-{i+1:02d}{img.suffix}")
        print(f"[render] 总时长={total_duration_s:.1f}s 总帧数={total_frames} 图片数={n_scenes}", flush=True)

        cover_trans_src = Path("intro_src/CoverTransition.tsx")
        if cover_trans_src.exists():
            _shutil.copy2(str(cover_trans_src), str(REMOTION_DIR / "src" / "CoverTransition.tsx"))

        story_cover_file = ""
        if img_files:
            _shutil.copy2(str(img_files[0]), str(REMOTION_DIR / "public" / "story_cover.jpg"))
            story_cover_file = "story_cover.jpg"
            print(f"[render] 书封已复制: {img_files[0].name}", flush=True)

        def to_subtitle_chunks(text: str, max_len: int = 18) -> list:
            sentences = [s.strip() for s in re.split(r'(?<=[。！？])', text.strip()) if s.strip()]
            chunks = []
            for sent in sentences:
                while len(sent) > max_len:
                    split_at = None
                    for j in range(min(max_len, len(sent) - 1), 0, -1):
                        if sent[j] in '，、；：':
                            split_at = j + 1
                            break
                    if split_at is None:
                        split_at = max_len
                    chunks.append(sent[:split_at])
                    sent = sent[split_at:]
                if sent:
                    chunks.append(sent)
            return [c.rstrip('。！？，、；：…—') for c in chunks]

        total_ms = int(total_duration_s * 1000)
        sub_chunks = to_subtitle_chunks(script.strip())
        total_chunk_chars = sum(len(c) for c in sub_chunks)
        subtitles = []
        cur_ms = 0
        for chunk in sub_chunks:
            dur_ms = int(total_ms * len(chunk) / total_chunk_chars) if total_chunk_chars else 2000
            subtitles.append({"text": chunk, "startMs": cur_ms, "endMs": cur_ms + dur_ms})
            cur_ms += dur_ms
        title_card_start_ms = int(intro_frames / FPS * 1000)
        title_card_end_ms   = title_card_start_ms + 2500

        scene_entries = []
        for i in range(n_scenes):
            scene_entries.append(
                f'  {{ id: "scene-{i+1:02d}", image: "{scene_images[i]}", '
                f'narration: "", durationInFrames: {scene_frames[i]} }}'
            )
        subtitle_entries = ",\n".join(
            f'  {{ text: {json.dumps(s["text"], ensure_ascii=False)}, startMs: {s["startMs"]}, endMs: {s["endMs"]} }}'
            for s in subtitles
        )
        content_ts = (
            'export type Scene = { id: string; image: string; narration: string; durationInFrames: number };\n'
            'export type Sub = { text: string; startMs: number; endMs: number };\n\n'
            'export const SCENES: Scene[] = [\n' + ',\n'.join(scene_entries) + '\n];\n\n'
            'export const SUBTITLES: Sub[] = [\n' + subtitle_entries + '\n];\n\n'
            f'export const TOTAL_FRAMES = {total_frames};\n'
            'export const AUDIO_FILE = "audio.mp3";\n'
            f'export const BOOK_TITLE = {json.dumps(title, ensure_ascii=False)};\n'
            f'export const TITLE_CARD_MS = {{ startMs: {title_card_start_ms}, endMs: {title_card_end_ms} }};\n'
            f'export const INTRO_FRAMES = {intro_frames};\n'
            f'export const STORY_COVER = {json.dumps(story_cover_file)};\n'
        )
        (REMOTION_DIR / "src" / "content.ts").write_text(content_ts, encoding="utf-8")
        print(f"[render] content.ts 已生成，字幕{len(subtitles)}句", flush=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        render_cmd = [
            "npx", "remotion", "render",
            "src/index.ts",
            "BookStory",
            str(output_path.resolve()),
        ]
        print(f"[render] 开始 Remotion 渲染…", flush=True)
        result = await run_subprocess(
            render_cmd, cwd=str(REMOTION_DIR),
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0 and output_path.exists():
            web_path = story_dir / "video_web.mp4"
            fs = await run_subprocess(
                ["ffmpeg", "-y", "-i", str(output_path),
                 "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                 "-pix_fmt", "yuv420p",
                 "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                 "-c:a", "aac", "-b:a", "128k",
                 "-movflags", "+faststart",
                 str(web_path)],
                capture_output=True, timeout=180
            )
            if fs.returncode == 0 and web_path.exists():
                web_path.replace(output_path)
                print(f"[render] ✓ 视频 web 优化完成", flush=True)

            c = get_db()
            c.execute("UPDATE stories SET video_path=?, status='done' WHERE id=?",
                      (str(output_path), story_id))
            c.commit(); c.close()
            print(f"[render] ✓ story {story_id}: 视频已保存 {output_path}", flush=True)
        else:
            err = (result.stderr or result.stdout or "未知错误")
            print(f"[render] Remotion 失败 (stdout):\n{result.stdout[-1000:]}", flush=True)
            print(f"[render] Remotion 失败 (stderr):\n{result.stderr[-1000:]}", flush=True)
            set_error(f"渲染失败: {err[-100:]}")

    except Exception as e:
        import traceback
        print(f"[render] 未捕获异常: {e}\n{traceback.format_exc()}", flush=True)
        try:
            set_error(f"渲染异常: {str(e)[:100]}")
        except Exception:
            pass


async def _run_pipeline(story_id: int):
    """一键全流程：脚本 → 并行(素材+封面+配音) → 合成视频"""
    print(f"[pipeline] ▶ story={story_id}", flush=True)
    row = db_get_story(story_id)
    if not row:
        print(f"[pipeline] story {story_id} not found", flush=True)
        return

    # Step 1: 生成脚本（如果还没有审核过的脚本）
    if row["status"] not in ("script_approved", "producing", "done"):
        await _run_generate(story_id)
        # pipeline 模式下自动审核，跳过人工审核
        c = get_db()
        c.execute("UPDATE stories SET status='script_approved' WHERE id=? AND status='script_draft'", (story_id,))
        c.commit(); c.close()

    # Step 2: 并行抓素材 + 封面 + 配音
    results = await asyncio.gather(
        _run_fetch(story_id),
        _run_cover(story_id),
        _run_tts(story_id),
        return_exceptions=True,
    )
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            step_name = ["fetch", "cover", "tts"][i]
            print(f"[pipeline] ⚠ {step_name} 步骤异常（已忽略）: {r}", flush=True)

    # Step 3: 合成视频
    await _run_render(story_id)
    print(f"[pipeline] ✓ story={story_id} 全流程完成", flush=True)


@app.post("/api/stories/{story_id}/run-pipeline")
async def api_run_pipeline(story_id: int, background_tasks: BackgroundTasks):
    row = db_get_story(story_id)
    if not row:
        raise HTTPException(404, "Story not found")
    if row["status"] not in ("research_done", "script_draft", "script_approved"):
        raise HTTPException(400, f"当前状态 {row['status']} 不支持一键生成")
    background_tasks.add_task(_run_pipeline, story_id)
    return {"ok": True, "message": "一键生成任务已启动"}


async def _run_book_pipeline(book_id: int):
    """从书籍维度一键全流程：自动创建故事 → 研究+脚本 → 自动审核 → 并行(素材+封面+配音) → 合成视频"""
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    latest_story = conn.execute(
        "SELECT id, status FROM stories WHERE book_id=? ORDER BY created_at DESC LIMIT 1",
        (book_id,)
    ).fetchone()
    conn.close()
    if not book:
        print(f"[book_pipeline] book {book_id} not found", flush=True)
        return

    # 如果已有可用状态的故事，直接走故事级 pipeline
    if latest_story and latest_story["status"] in ("research_done", "script_draft", "script_approved"):
        await _run_pipeline(latest_story["id"])
        return

    # 需要从头创建故事
    if not latest_story or latest_story["status"] == "failed":
        conn = get_db()
        used = {r["angle"] for r in conn.execute(
            "SELECT angle FROM stories WHERE book_id=?", (book_id,)
        ).fetchall()}
        conn.close()
        available = [a for a in STORY_ANGLES if a not in used] or list(STORY_ANGLES)
        angle = available[0]
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO stories(book_id, angle, status) VALUES(?,?,?)",
            (book_id, angle, "pending_research")
        )
        story_id = cur.lastrowid
        conn.commit(); conn.close()
        story_dir = STORIES_DIR / str(story_id)
        story_dir.mkdir(exist_ok=True)
        (story_dir / "assets").mkdir(exist_ok=True)
        print(f"[book_pipeline] ▶ book={book_id} 创建故事 story={story_id} 角度={angle}", flush=True)
    else:
        story_id = latest_story["id"]
        print(f"[book_pipeline] ▶ book={book_id} 使用现有故事 story={story_id}", flush=True)

    # 运行发现流程（研究 + 脚本）
    await discover_story_bg(book_id, story_id)

    # 检查是否成功生成脚本
    row = db_get_story(story_id)
    if not row or row["status"] == "failed":
        print(f"[book_pipeline] story {story_id} 研究/脚本失败，中止", flush=True)
        return

    # 自动审核
    conn = get_db()
    conn.execute(
        "UPDATE stories SET status='script_approved' WHERE id=? AND status='script_draft'",
        (story_id,)
    )
    conn.commit(); conn.close()

    # 并行：素材 + 封面 + 配音
    results = await asyncio.gather(
        _run_fetch(story_id),
        _run_cover(story_id),
        _run_tts(story_id),
        return_exceptions=True,
    )
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"[book_pipeline] ⚠ {['fetch','cover','tts'][i]} 异常: {r}", flush=True)

    # 合成视频
    await _run_render(story_id)
    print(f"[book_pipeline] ✓ book={book_id} story={story_id} 全流程完成", flush=True)


@app.post("/api/books/{book_id}/run-pipeline")
async def api_book_run_pipeline(book_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    book = conn.execute("SELECT id FROM books WHERE id=?", (book_id,)).fetchone()
    latest_story = conn.execute(
        "SELECT id, status FROM stories WHERE book_id=? ORDER BY created_at DESC LIMIT 1",
        (book_id,)
    ).fetchone()
    conn.close()
    if not book:
        raise HTTPException(404, "Book not found")
    # 正在进行中时不允许重复触发
    if latest_story and latest_story["status"] in ("researching", "scripting", "producing"):
        raise HTTPException(400, f"当前状态 {latest_story['status']} 不支持一键生成，请等待完成")
    background_tasks.add_task(_run_book_pipeline, book_id)
    return {"ok": True, "message": "一键生成任务已启动"}


# ── 豆瓣 Top250 导入 ──────────────────────────────────────────────────────────
@app.post("/api/books/import-douban-top250")
async def api_import_douban(background_tasks: BackgroundTasks):
    async def do_import():
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        imported = 0
        for start in range(0, 250, 25):
            try:
                async with httpx.AsyncClient(timeout=20, headers=headers) as client:
                    r = await client.get("https://book.douban.com/top250", params={"start": start})
                if r.status_code != 200:
                    print(f"[douban] start={start} status={r.status_code}", flush=True)
                    await asyncio.sleep(3)
                    continue
                subjects = re.findall(
                    r'<div class="pl2">.*?<a[^>]+href="(https://book\.douban\.com/subject/(\d+)/[^"]*)"[^>]*>\s*([^<\n]+)',
                    r.text, re.DOTALL
                )
                for url, douban_id, title in subjects:
                    title = title.strip()
                    if not title or not douban_id:
                        continue
                    conn = get_db()
                    exists = conn.execute("SELECT id FROM books WHERE weread_id=?",
                                         (f"douban_{douban_id}",)).fetchone()
                    if not exists:
                        conn.execute(
                            "INSERT OR IGNORE INTO books(weread_id, title, book_pipeline_status) VALUES(?,?,?)",
                            (f"douban_{douban_id}", title, "unscored")
                        )
                        conn.commit()
                        imported += 1
                    conn.close()
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[douban] error at start={start}: {e}", flush=True)
        print(f"[douban] import done: {imported} books", flush=True)

    background_tasks.add_task(do_import)
    return {"ok": True, "message": "豆瓣Top250导入任务已启动"}

# ── 批量故事潜力评分 ──────────────────────────────────────────────────────────
@app.post("/api/books/batch-score-story")
async def api_batch_score_story(background_tasks: BackgroundTasks):
    conn = get_db()
    unscored = conn.execute(
        "SELECT id FROM books WHERE story_score IS NULL OR book_pipeline_status='unscored'"
    ).fetchall()
    conn.close()
    ids = [r["id"] for r in unscored]

    async def do_batch():
        for book_id in ids:
            try:
                conn = get_db()
                book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
                conn.close()
                if not book:
                    continue
                prompt = STORY_POTENTIAL_PROMPT.format(
                    title=book["title"],
                    author=book["author"] or "未知",
                    intro=book["intro"] or "暂无简介",
                )
                text = await kimi_chat(prompt, temperature=1)
                result = parse_json_response(text)
                score = int(result.get("score", 5))
                reason = result.get("reason", "")
                pipeline_status = "ready" if score >= 6 else "low_potential"
                c = get_db()
                c.execute(
                    "UPDATE books SET story_score=?, story_score_reason=?, book_pipeline_status=? WHERE id=?",
                    (score, reason, pipeline_status, book_id)
                )
                c.commit(); c.close()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[batch-score] book {book_id}: {e}", flush=True)

    background_tasks.add_task(do_batch)
    return {"ok": True, "queued": len(ids)}

# ── 一键发现故事 ──────────────────────────────────────────────────────────────
async def discover_story_bg(book_id: int, story_id: int):
    """后台执行：搜索 → 研究 → AI提炼角度 → 写脚本，一次完成。"""
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    conn.close()
    if not book:
        print(f"[discover] book {book_id} not found, abort", flush=True)
        return

    title = book["title"]
    author = book["author"] or ""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[discover] ▶ 开始 story={story_id} 《{title}》{author}", flush=True)

    c = get_db()
    c.execute("UPDATE stories SET status='researching', daily_date=? WHERE id=?", (today, story_id))
    c.commit(); c.close()

    raw_data = {"searches": [], "wikipedia": {}}

    # 1. Brave Search（5个查询）
    queries = [
        f'"{title}" {author} 出版故事 写作经历',
        f'"{title}" {author} 被禁 审查 争议',
        f'"{title}" {author} 书名来历 创作背景',
        f'"{title}" {author} banned censored history',
        f'"{title}" {author} behind the scenes story',
    ]
    print(f"[discover] 1/3 Brave搜索 ({len(queries)}条)…", flush=True)
    for q in queries:
        results = await brave_search(q)
        print(f"[discover]   query={q!r} → {len(results)}条结果", flush=True)
        for item in results[:2]:
            page_text = await fetch_page_text(item.get("url", ""))
            raw_data["searches"].append({
                "query": q,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "text": page_text[:2000],
            })
        await asyncio.sleep(0.3)
    print(f"[discover]   搜索完成，收集{len(raw_data['searches'])}条片段", flush=True)

    # 2. Wikipedia（中英文，书名+作者）
    print(f"[discover] 2/3 Wikipedia…", flush=True)
    for lang, search_title in [("zh", title), ("en", title), ("zh", author), ("en", author)]:
        if not search_title:
            continue
        extract = await wikipedia_extract(search_title, lang)
        if extract:
            raw_data["wikipedia"][f"{lang}:{search_title}"] = extract
            print(f"[discover]   wiki {lang}:{search_title} → {len(extract)}字", flush=True)

    # 保存原始数据
    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "research_raw.json").write_text(
        json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3. 拼合所有资料，交给Kimi一次性处理（过滤敏感来源）
    BLOCKED_DOMAINS = ["chinadigitaltimes", "rfa.org", "voachinese", "bbc.com/zhongwen",
                       "dw.com/zh", "theinitium", "matters.news", "github.com/ciaa"]
    combined = ""
    for s in raw_data["searches"]:
        url = s.get("url", "")
        if any(d in url for d in BLOCKED_DOMAINS):
            print(f"[discover]   跳过敏感来源: {url}", flush=True)
            continue
        snippet = s["description"] or s["text"][:500]
        if snippet:
            combined += f"\n--- 搜索结果: {s['title']} ---\n{snippet}\n"
    for k, v in raw_data["wikipedia"].items():
        combined += f"\n--- Wikipedia ({k}) ---\n{v}\n"

    if not combined.strip():
        combined = f"书名：《{title}》，作者：{author}。暂无网络资料，请基于已知知识创作。"

    print(f"[discover] 3/3 调用Kimi（素材{len(combined)}字）…", flush=True)
    prompt = DISCOVER_STORY_PROMPT.format(
        title=title, author=author or "未知",
        raw_content=combined[:15000],
    )

    try:
        kimi_text = await kimi_chat(prompt, temperature=1)
        result = parse_json_response(kimi_text)
        angle = result.get("angle", "写作故事")
        facts = result.get("facts", [])
        script = result.get("script", "")

        summary = {"facts": facts, "summary": f"角度：{angle}\n" + "\n".join(f"- {f}" for f in facts)}

        (story_dir / "research_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if script:
            script = add_script_intro(script, title)
            (story_dir / "script_draft.txt").write_text(script, encoding="utf-8")

        c = get_db()
        c.execute(
            """UPDATE stories SET angle=?, research_raw=?, research_summary=?,
               script=?, status='script_draft' WHERE id=?""",
            (angle, json.dumps(raw_data, ensure_ascii=False),
             json.dumps(summary, ensure_ascii=False), script, story_id)
        )
        c.commit(); c.close()
        print(f"[discover] ✓ 完成 story={story_id} 角度={angle} 脚本{len(script)}字", flush=True)
    except Exception as e:
        err = str(e)
        print(f"[discover] ✗ 失败 story={story_id}: {err}", flush=True)
        c = get_db()
        c.execute("UPDATE stories SET status='failed', error_msg=? WHERE id=?", (err, story_id))
        c.commit(); c.close()


@app.post("/api/books/{book_id}/discover-story")
async def api_discover_story(book_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    conn.close()
    if not book:
        raise HTTPException(404, "书籍不存在")

    # 创建故事记录（角度由AI决定，先用占位符）
    today = datetime.now().strftime("%Y-%m-%d")
    c = get_db()
    cur = c.execute(
        "INSERT INTO stories(book_id, angle, status, daily_date) VALUES(?,?,?,?)",
        (book_id, "发现中…", "researching", today)
    )
    story_id = cur.lastrowid
    c.commit(); c.close()

    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "assets").mkdir(exist_ok=True)

    background_tasks.add_task(discover_story_bg, book_id, story_id)
    return {"ok": True, "story_id": story_id, "message": "AI正在发现故事，约2-5分钟后刷新"}


# ── 今日任务 ──────────────────────────────────────────────────────────────────
def pick_today_book() -> Optional[dict]:
    """选书逻辑：从未做过故事的书中选，经典:热门 = 3:1 轮转。"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()

    # 今天已选的书
    today_story = conn.execute(
        """SELECT s.book_id, b.title, b.author, b.book_type FROM stories s
           JOIN books b ON s.book_id = b.id
           WHERE s.daily_date=? LIMIT 1""", (today,)
    ).fetchone()
    if today_story:
        conn.close()
        return dict(today_story)

    # 统计已做过故事的书
    done_ids = {r[0] for r in conn.execute(
        "SELECT DISTINCT book_id FROM stories WHERE status NOT IN ('pending_research')"
    ).fetchall()}

    # 统计最近选了多少经典/热门
    recent = conn.execute(
        """SELECT b.book_type, COUNT(*) as cnt FROM stories s
           JOIN books b ON s.book_id = b.id
           WHERE s.daily_date IS NOT NULL
           GROUP BY b.book_type"""
    ).fetchall()
    type_counts = {r["book_type"]: r["cnt"] for r in recent}
    classic_cnt = type_counts.get("classic", 0)
    trending_cnt = type_counts.get("trending", 0)

    # 3:1 比例：当trending未达到应有比例时选trending，否则选classic
    total = classic_cnt + trending_cnt
    want_trending = (total + 1) // 4  # every 4th book is trending
    prefer_trending = trending_cnt < want_trending

    all_books = conn.execute("SELECT * FROM books ORDER BY created_at DESC").fetchall()
    conn.close()

    candidates_preferred = []
    candidates_fallback = []
    for b in all_books:
        if b["id"] in done_ids:
            continue
        if prefer_trending and b["book_type"] == "trending":
            candidates_preferred.append(dict(b))
        elif not prefer_trending and b["book_type"] == "classic":
            candidates_preferred.append(dict(b))
        else:
            candidates_fallback.append(dict(b))

    pool = candidates_preferred or candidates_fallback
    if not pool:
        return None
    # 选第一本（按created_at DESC，最新导入的先用）
    return pool[0]


@app.get("/api/today")
def api_today():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()

    # 今天有无进行中故事
    story = conn.execute(
        """SELECT s.*, b.title as book_title, b.author as book_author
           FROM stories s JOIN books b ON s.book_id = b.id
           WHERE s.daily_date=?
           ORDER BY s.created_at DESC LIMIT 1""", (today,)
    ).fetchone()
    conn.close()

    if story:
        s = dict(story)
        return {
            "date": today,
            "has_story": True,
            "story": s,
            "phase": _story_phase(s["status"]),
        }

    recommended = pick_today_book()
    return {
        "date": today,
        "has_story": False,
        "recommended_book": recommended,
        "phase": "not_started",
    }


def _story_phase(status: str) -> str:
    if status in ("researching", "scripting"):
        return "in_progress"
    if status == "script_draft":
        return "pending_review"
    if status in ("script_approved", "producing", "done", "published"):
        return "done"
    return "in_progress"


@app.post("/api/today/start")
async def api_today_start(body: dict, background_tasks: BackgroundTasks):
    """选书 + 触发 discover-story。"""
    book_id = body.get("book_id")
    if book_id:
        conn = get_db()
        book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        conn.close()
        if not book:
            raise HTTPException(404, "书籍不存在")
    else:
        book = pick_today_book()
        if not book:
            raise HTTPException(400, "书库为空，请先导入书目")
        book_id = book["id"] if isinstance(book, dict) else book["id"]

    today = datetime.now().strftime("%Y-%m-%d")
    c = get_db()
    cur = c.execute(
        "INSERT INTO stories(book_id, angle, status, daily_date) VALUES(?,?,?,?)",
        (book_id, "发现中…", "researching", today)
    )
    story_id = cur.lastrowid
    c.commit(); c.close()

    story_dir = STORIES_DIR / str(story_id)
    story_dir.mkdir(exist_ok=True)
    (story_dir / "assets").mkdir(exist_ok=True)

    background_tasks.add_task(discover_story_bg, book_id, story_id)
    return {"ok": True, "story_id": story_id, "book_id": book_id}


# ── 书库扩充：获奖书单 ────────────────────────────────────────────────────────
@app.post("/api/books/import-awards")
def api_import_awards():
    conn = get_db()
    imported = 0
    for b in AWARDS_BOOKS:
        weread_id = f"award_{b['title'].replace(' ', '_')}"
        exists = conn.execute("SELECT id FROM books WHERE weread_id=?", (weread_id,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT OR IGNORE INTO books(weread_id, title, author, book_type, intro) VALUES(?,?,?,?,?)",
                (weread_id, b["title"], b["author"], "classic", b.get("award", ""))
            )
            imported += 1
    conn.commit()
    conn.close()
    return {"ok": True, "imported": imported, "total": len(AWARDS_BOOKS)}


# ── 书库扩充：本月热门 ────────────────────────────────────────────────────────
@app.post("/api/books/import-trending")
async def api_import_trending(background_tasks: BackgroundTasks):
    async def do_import():
        queries = ["2025年畅销书单 豆瓣", "近期热门文学小说推荐", "当下流行书籍排行榜"]
        raw_titles = []
        for q in queries:
            results = await brave_search(q)
            for item in results[:4]:
                # 只保留标题和摘要，截断过长内容，降低 Kimi 风控触发概率
                snippet = (item.get("title", "") + " " + item.get("description", ""))[:200]
                raw_titles.append(snippet)

        if not raw_titles:
            print("[trending] no search results", flush=True)
            return

        combined = "\n".join(raw_titles[:12])
        prompt = f"""以下是书籍相关搜索摘要，请从中识别并列出10-20本书的书名和作者。
仅输出书名和作者，忽略无关内容。

摘要：
{combined}

返回JSON：{{"books": [{{"title": "书名", "author": "作者"}}]}}"""

        try:
            text = await kimi_chat(prompt, temperature=1)
            result = parse_json_response(text)
            books = result.get("books", [])
            conn = get_db()
            imported = 0
            for b in books:
                title = b.get("title", "").strip()
                author = b.get("author", "").strip()
                if not title:
                    continue
                weread_id = f"trending_{title}"
                exists = conn.execute("SELECT id FROM books WHERE weread_id=?", (weread_id,)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT OR IGNORE INTO books(weread_id, title, author, book_type) VALUES(?,?,?,?)",
                        (weread_id, title, author, "trending")
                    )
                    imported += 1
            conn.commit(); conn.close()
            print(f"[trending] imported {imported} books", flush=True)
        except Exception as e:
            print(f"[trending] error: {e}", flush=True)

    background_tasks.add_task(do_import)
    return {"ok": True, "message": "热门书目搜索中，约1分钟后刷新"}


# ── 书库扩充：话题关联书 ──────────────────────────────────────────────────────
class TopicIn(BaseModel):
    topic: str


@app.post("/api/books/import-topic")
async def api_import_topic(body: TopicIn, background_tasks: BackgroundTasks):
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(400, "topic不能为空")

    async def do_import():
        prompt = f"""你是书单专家，请推荐10-15本与「{topic}」主题最相关的经典书籍（中外均可）。
要求：有真实历史背景、适合制作「书背后的故事」短视频。

严格返回JSON：{{"books": [{{"title": "书名", "author": "作者", "reason": "关联原因"}}]}}"""

        try:
            text = await kimi_chat(prompt, temperature=1)
            result = parse_json_response(text)
            books = result.get("books", [])
            conn = get_db()
            imported = 0
            for b in books:
                title = b.get("title", "").strip()
                author = b.get("author", "").strip()
                if not title:
                    continue
                weread_id = f"topic_{topic}_{title}"
                exists = conn.execute("SELECT id FROM books WHERE weread_id=?", (weread_id,)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT OR IGNORE INTO books(weread_id, title, author, book_type, intro) VALUES(?,?,?,?,?)",
                        (weread_id, title, author, "classic", b.get("reason", ""))
                    )
                    imported += 1
            conn.commit(); conn.close()
            print(f"[topic:{topic}] imported {imported} books", flush=True)
        except Exception as e:
            print(f"[topic] error: {e}", flush=True)

    background_tasks.add_task(do_import)
    return {"ok": True, "message": f"「{topic}」相关书目生成中，约30秒后刷新"}


# ── 静态文件 ──────────────────────────────────────────────────────────────────
app.mount("/data", StaticFiles(directory="data"), name="data")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
