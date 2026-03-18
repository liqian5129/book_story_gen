# 书背后的故事

抖音短视频自动化生产系统。从微信读书书单出发，全自动完成选题研究 → AI写稿 → 语音克隆 → 视频合成的完整流水线，无需出镜。

## 功能概览

- **书单管理**：从豆瓣 Top250 批量导入，或手动添加书目，AI 自动评估故事潜力
- **金句库**：抓取微信读书划线高亮，AI 评分筛选
- **故事工坊**：选择故事角度，一键触发 研究 → 写稿 → 配音 → 合成 全流程
- **导出**：生成成片，发布抖音

### 支持的故事角度

`书名秘密` · `写作故事` · `被禁历程` · `差点没出版` · `角色原型` · `作者命运`

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python · FastAPI · SQLite |
| 前端 | 原生 HTML/CSS/JS（单页应用） |
| AI   | Kimi/Moonshot（kimi-k2）|
| 搜索 | Brave Search API · Wikipedia · Wikimedia Commons |
| 配音 | 火山引擎 TTS（声音克隆）|
| 视频 | Remotion（React 渲染）|
| 书源 | 微信读书 · 豆瓣 Top250 |

## 快速开始

**1. 配置环境变量**

```bash
cp .env.example .env
# 编辑 .env，填入各项 API Key
```

**2. 启动服务**

```bash
./start.sh
```

访问 `http://localhost:8888`

## 环境变量说明

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `WEREAD_COOKIES` | 微信读书登录 Cookie | 浏览器开发者工具 |
| `KIMI_API_KEY` | Kimi AI 接口密钥 | [platform.moonshot.cn](https://platform.moonshot.cn) |
| `BRAVE_API_KEY` | Brave 搜索（免费 2000次/月）| [brave.com/search/api](https://brave.com/search/api) |
| `VOLC_APPID` | 火山引擎 TTS App ID | [console.volcengine.com](https://console.volcengine.com) |
| `VOLC_TOKEN` | 火山引擎 TTS Token | 同上 |
| `VOLC_VOICE_TYPE` | 克隆音色 ID | 同上 |
| `PORT` | 服务端口（默认 8888）| — |

## 项目结构

```
.
├── server.py                  # FastAPI 后端（单文件）
├── start.sh                   # 一键启动脚本
├── requirements.txt           # Python 依赖
├── static/                    # 前端静态文件
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/
│   ├── book-story-video/      # Remotion 视频合成项目
│   └── stories/               # 生成的故事素材（已 gitignore）
├── piantou/                   # 片头 Remotion 项目
└── .env.example               # 环境变量模板
```

## 故事生产流水线

```
pending_research
      ↓
  researching  ←─ Brave Search + Wikipedia
      ↓
 research_done
      ↓
  scripting    ←─ Kimi AI 写稿
      ↓
 script_draft
      ↓
script_approved ←─ 人工审核
      ↓
  producing    ←─ 火山引擎 TTS + Remotion
      ↓
    done
      ↓
  published    ←─ 发布抖音
```
