// ── API ───────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch("/api" + path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}
const get   = p      => api("GET",    p);
const post  = (p, b) => api("POST",   p, b);
const patch = (p, b) => api("PATCH",  p, b);
const del   = p      => api("DELETE", p);

// ── Toast ─────────────────────────────────────────────────────────────────────
let _toastTimer;
function toast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

function esc(s) {
  return s ? String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;") : "";
}

// ── 常量 ──────────────────────────────────────────────────────────────────────
const ANGLES = {
  "书名秘密":  "书名的来历或隐藏含义",
  "写作故事":  "作者写作时的特殊经历",
  "被禁历程":  "被禁、审查或引发争议",
  "差点没出版": "出版波折，险些未能面世",
  "角色原型":  "书中人物的现实原型",
  "作者命运":  "作者的戏剧性人生经历",
};

const STATUS_LABEL = {
  pending_research: "待研究",
  researching:      "研究中…",
  research_done:    "研究完成",
  scripting:        "生成中…",
  script_draft:     "待审核",
  script_approved:  "待制作",
  producing:        "制作中",
  done:             "已完成",
  published:        "已发布",
  failed:           "失败",
};

// ── 今日任务面板 ──────────────────────────────────────────────────────────────
async function loadTodayPanel() {
  const el = document.getElementById("today-content");
  try {
    const data = await get("/today");
    if (data.has_story) {
      const s = data.story;
      const phase = data.phase;
      if (phase === "in_progress") {
        el.innerHTML = `
          <div class="today-phase today-inprogress">
            <span class="today-label">进行中</span>
            <span class="today-book">正在发现《${esc(s.book_title)}》的故事…</span>
            <span class="today-spinner">◌◌◌</span>
          </div>`;
      } else if (phase === "pending_review") {
        el.innerHTML = `
          <div class="today-phase today-review">
            <span class="today-label">待审核</span>
            <span class="today-book">《${esc(s.book_title)}》· 角度：${esc(s.angle)}</span>
            <button class="btn-sm btn-primary" onclick="openScriptModal(${s.id})">打开审核脚本 →（约5分钟）</button>
          </div>`;
      } else {
        el.innerHTML = `
          <div class="today-phase today-done">
            <span class="today-label">今日已完成</span>
            <span class="today-book">《${esc(s.book_title)}》· ${esc(s.angle)}</span>
            <button class="btn-sm" onclick="openScriptModal(${s.id})">查看脚本</button>
          </div>`;
      }
    } else {
      const rec = data.recommended_book;
      const bookName = rec ? `《${esc(rec.title)}》` : "（书库为空）";
      const bookType = rec ? rec.book_type : "";
      const typeTag = bookType === "trending" ? `<span class="today-tag-trending">热门</span>` : `<span class="today-tag-classic">经典</span>`;
      el.innerHTML = `
        <div class="today-phase today-notstarted">
          <span class="today-label">今日任务</span>
          <span class="today-book">推荐：${bookName} ${rec ? typeTag : ""}</span>
          <div class="today-actions">
            ${rec ? `<button class="btn-sm btn-primary" id="btn-today-start" data-id="${rec.id}">▶ AI自动发现故事</button>` : ""}
            ${rec ? `<button class="btn-sm" id="btn-today-change">换一本 ↻</button>` : ""}
          </div>
        </div>`;
      document.getElementById("btn-today-start")?.addEventListener("click", async e => {
        const btn = e.currentTarget;
        btn.disabled = true; btn.textContent = "启动中…";
        try {
          await post("/today/start", { book_id: parseInt(btn.dataset.id) });
          toast("AI已开始发现故事，约3分钟后刷新");
          setTimeout(loadTodayPanel, 3000);
        } catch (err) { toast(err.message, true); btn.disabled = false; btn.textContent = "▶ AI自动发现故事"; }
      });
      document.getElementById("btn-today-change")?.addEventListener("click", async () => {
        // 刷新推荐（后端 pick_today_book 不固定，随机从pool取第一个即可，
        // 这里简单跳过当前推荐再请求会复杂，暂用discover直接选下一本）
        toast("暂无换书功能，请手动点击书库中的书再触发发现故事");
      });
    }
  } catch (e) {
    el.innerHTML = `<span style="color:var(--text-muted);font-size:12px">今日面板加载失败：${e.message}</span>`;
  }
}

// ── 书库 ──────────────────────────────────────────────────────────────────────
let _selectedBookId = null;

async function loadBooks() {
  const el = document.getElementById("book-list");
  try {
    const books = await get("/books");
    document.getElementById("book-count").textContent = books.length;
    if (!books.length) {
      el.innerHTML = `<div class="empty">点击「导入豆瓣Top250」或「导入获奖书单」开始</div>`;
      return;
    }
    el.innerHTML = books.map(b => {
      const wid = b.weread_id || "";
      let sourceTag;
      if (wid.startsWith("douban_")) {
        sourceTag = `<span class="book-type-douban">豆瓣Top</span>`;
      } else if (wid.startsWith("award_")) {
        sourceTag = `<span class="book-type-award">获奖书</span>`;
      } else if (b.book_type === "trending") {
        sourceTag = `<span class="book-type-trending">微信热读</span>`;
      } else {
        sourceTag = `<span class="book-type-classic">经典</span>`;
      }
      const researchedDot = b.researched_count > 0
        ? `<span class="book-researched-dot" title="已研究">✦</span>`
        : "";
      // 进行中时不显示按钮，其他状态（含无故事）都显示
      const busyStatuses = ["researching","scripting","producing","done","published"];
      const pipelineBtn = !busyStatuses.includes(b.latest_story_status)
        ? `<button class="btn-sm btn-pipeline pipeline-btn" data-book-id="${b.id}" title="一键生成：研究→脚本→配音→封面→视频">⚡</button>`
        : "";
      return `
      <div class="book-item ${_selectedBookId == b.id ? 'active' : ''}" data-id="${b.id}">
        ${b.cover ? `<img class="book-cover-sm" src="${esc(b.cover)}" onerror="this.style.display='none'">` : ""}
        <div class="book-item-info">
          <div class="book-item-title">${esc(b.title)} ${researchedDot}</div>
          <div class="book-item-sub">
            ${sourceTag}
            <span>${esc(b.author || "")}</span>
          </div>
        </div>
        <div class="book-item-actions">
          <button class="btn-sm btn-ai discover-btn" data-id="${b.id}" data-title="${esc(b.title)}" title="AI自动发现故事">✦</button>
          <button class="btn-sm btn-primary create-btn" data-id="${b.id}" data-title="${esc(b.title)}" title="手动创建故事">+</button>
          ${pipelineBtn}
        </div>
      </div>`;
    }).join("");

    el.querySelectorAll(".book-item").forEach(item => {
      item.addEventListener("click", e => {
        if (e.target.closest("button")) return;
        _selectedBookId = parseInt(item.dataset.id);
        loadStories();
        el.querySelectorAll(".book-item").forEach(i => i.classList.remove("active"));
        item.classList.add("active");
      });
    });

    el.querySelectorAll(".discover-btn").forEach(btn => {
      btn.addEventListener("click", async e => {
        e.stopPropagation();
        btn.disabled = true; btn.textContent = "…";
        try {
          await post(`/books/${btn.dataset.id}/discover-story`, {});
          toast(`正在发现《${btn.dataset.title}》的故事，约3分钟后刷新`);
          setTimeout(loadStories, 3000);
          loadTodayPanel();
        } catch (err) { toast(err.message, true); btn.disabled = false; btn.textContent = "✦"; }
      });
    });

    el.querySelectorAll(".create-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        openAngleModal(btn.dataset.id, btn.dataset.title);
      });
    });

    el.querySelectorAll(".pipeline-btn").forEach(btn => {
      btn.addEventListener("click", async e => {
        e.stopPropagation();
        const bookId = btn.dataset.bookId;
        btn.disabled = true; btn.textContent = "生成中…";
        try {
          await post(`/books/${bookId}/run-pipeline`, {});
          toast("一键生成任务已启动，约3-8分钟完成");
          // 轮询：刷新书单 + 故事列表直到完成
          const poll = setInterval(async () => {
            try {
              loadBooks();
              if (_selectedBookId == bookId) loadStories();
            } catch (_) {}
          }, 8000);
          setTimeout(() => { clearInterval(poll); loadBooks(); }, 720000);
        } catch (e) {
          toast(e.message, true);
          btn.disabled = false; btn.textContent = "⚡";
        }
      });
    });

  } catch (e) {
    el.innerHTML = `<div class="empty">${e.message}</div>`;
  }
}

// ── 添加书（手动）────────────────────────────────────────────────────────────
document.getElementById("btn-show-add").addEventListener("click", () => {
  document.getElementById("add-book-panel").classList.toggle("hidden");
});
document.getElementById("btn-cancel-add").addEventListener("click", () => {
  document.getElementById("add-book-panel").classList.add("hidden");
});
document.getElementById("btn-add-book").addEventListener("click", async () => {
  const title  = document.getElementById("add-title").value.trim();
  const author = document.getElementById("add-author").value.trim();
  if (!title) { toast("请输入书名", true); return; }
  try {
    await post("/books", { weread_id: `manual_${Date.now()}`, title, author });
    toast(`《${title}》已添加`);
    document.getElementById("add-title").value = "";
    document.getElementById("add-author").value = "";
    document.getElementById("add-book-panel").classList.add("hidden");
    loadBooks();
  } catch (e) { toast(e.message, true); }
});

// ── 导入书目 ──────────────────────────────────────────────────────────────────
document.getElementById("btn-import-douban").addEventListener("click", async () => {
  const btn = document.getElementById("btn-import-douban");
  btn.disabled = true; btn.textContent = "导入中…";
  try {
    await post("/books/import-douban-top250", {});
    toast("豆瓣Top250导入中，约1分钟后刷新");
    setTimeout(loadBooks, 8000);
  } catch (e) { toast(e.message, true); }
  setTimeout(() => { btn.disabled = false; btn.textContent = "导入豆瓣Top250"; }, 4000);
});

document.getElementById("btn-setup-remotion").addEventListener("click", async () => {
  const btn = document.getElementById("btn-setup-remotion");
  btn.disabled = true; btn.textContent = "初始化中…";
  try {
    await post("/setup-remotion", {});
    toast("Remotion 项目初始化中，npm install 约需1-2分钟，请查看终端日志");
  } catch (e) { toast(e.message, true); }
  setTimeout(() => { btn.disabled = false; btn.textContent = "⚙ 初始化视频项目"; }, 5000);
});

document.getElementById("btn-import-awards").addEventListener("click", async () => {
  const btn = document.getElementById("btn-import-awards");
  btn.disabled = true; btn.textContent = "导入中…";
  try {
    const r = await post("/books/import-awards", {});
    toast(`获奖书单已导入 ${r.imported} 本（共${r.total}本）`);
    loadBooks();
  } catch (e) { toast(e.message, true); }
  setTimeout(() => { btn.disabled = false; btn.textContent = "导入获奖书单"; }, 2000);
});

document.getElementById("btn-import-trending").addEventListener("click", async () => {
  const btn = document.getElementById("btn-import-trending");
  btn.disabled = true; btn.textContent = "搜索中…";
  try {
    await post("/books/import-trending", {});
    toast("热门书目搜索中，约1分钟后刷新");
    setTimeout(loadBooks, 60000);
  } catch (e) { toast(e.message, true); }
  setTimeout(() => { btn.disabled = false; btn.textContent = "导入热门书"; }, 4000);
});

// ── 角度选择弹窗 ──────────────────────────────────────────────────────────────
let _angleBookId = null;

function openAngleModal(bookId, bookTitle) {
  _angleBookId = bookId;
  document.getElementById("angle-modal-title").textContent = `《${bookTitle}》— 选择故事角度`;
  document.getElementById("angle-list").innerHTML = Object.entries(ANGLES).map(([name, desc]) => `
    <div class="angle-item" data-angle="${name}">
      <span class="angle-name">${name}</span>
      <span class="angle-desc">${desc}</span>
    </div>
  `).join("");
  document.querySelectorAll(".angle-item").forEach(item => {
    item.addEventListener("click", async () => {
      const angle = item.dataset.angle;
      try {
        await post("/stories", { book_id: parseInt(_angleBookId), angle });
        toast(`已创建「${angle}」故事`);
        closeAngleModal();
        loadStories();
        loadBooks();
      } catch (e) { toast(e.message, true); }
    });
  });
  document.getElementById("angle-modal").classList.remove("hidden");
}

function closeVideoModal() {
  const player = document.getElementById("video-player");
  player.pause();
  player.src = "";
  document.getElementById("video-modal").classList.add("hidden");
}
document.getElementById("video-modal").addEventListener("click", function(e) {
  if (e.target === this) closeVideoModal();
});

function closeAngleModal() {
  document.getElementById("angle-modal").classList.add("hidden");
  _angleBookId = null;
}

document.getElementById("angle-modal").addEventListener("click", e => {
  if (e.target === document.getElementById("angle-modal")) closeAngleModal();
});

// ── 故事流水线 ────────────────────────────────────────────────────────────────
document.getElementById("btn-refresh-stories").addEventListener("click", loadStories);
document.getElementById("story-filter").addEventListener("change", loadStories);

async function loadStories() {
  const el = document.getElementById("story-list");
  const scrollY = window.scrollY;
  el.innerHTML = `<div class="loading"><span class="spinning">⟳</span> 加载中…</div>`;
  try {
    const status = document.getElementById("story-filter").value;
    let url = "/stories";
    const params = [];
    if (_selectedBookId) params.push(`book_id=${_selectedBookId}`);
    if (status) params.push(`status=${status}`);
    if (params.length) url += "?" + params.join("&");

    const stories = await get(url);
    if (!stories.length) {
      el.innerHTML = `<div class="empty">暂无故事${_selectedBookId ? "，点左侧「+」创建" : ""}</div>`;
      return;
    }
    el.innerHTML = stories.map(renderStoryCard).join("");
    attachStoryEvents();
    window.scrollTo({ top: scrollY, behavior: "instant" });
    _lastStoryStatuses = Object.fromEntries(stories.map(s => [s.id, s.status]));
  } catch (e) {
    el.innerHTML = `<div class="empty">${e.message}</div>`;
  }
}

function renderStoryCard(s) {
  const summary = s.research_summary ? (() => { try { return JSON.parse(s.research_summary); } catch { return null; } })() : null;
  let assets = []; try { assets = JSON.parse(s.assets || "[]"); } catch {}
  const hasAudio = !!s.audio_path;
  const hasVideo = !!s.video_path;

  let content = "";

  // 研究摘要
  if (summary && summary.facts && summary.facts.length) {
    content += `<div class="facts-box">${summary.facts.slice(0,3).map(f => `· ${esc(f)}`).join("<br>")}</div>`;
  }

  // 脚本预览
  if (s.script && ["script_draft","script_approved","producing","done","published"].includes(s.status)) {
    const wc = s.script.length;
    const sec = Math.round(wc / 4.5);
    const isApproved = ["script_approved","producing","done","published"].includes(s.status);
    content += `
    <div class="script-preview">${esc(s.script.slice(0, 200))}${s.script.length > 200 ? "…" : ""}</div>
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">${wc}字 · 约${sec}秒
      ${isApproved ? `<button class="btn-sm view-script-btn" data-id="${s.id}" style="margin-left:8px">查看全文</button>` : ""}
    </div>`;
  }

  // 制作步骤
  if (["script_approved","producing","done","published"].includes(s.status)) {
    const coverSrc = s.cover_path ? `/${s.cover_path}?t=${s.updated_at||s.id}` : "";
    content += `<div class="produce-steps">
      <div class="assets-cover-row">
        <div class="assets-col">
          <div class="produce-step ${assets.length ? 'done' : ''}">
            <span class="step-icon">${assets.length ? "✓" : "○"}</span>
            <span>素材 (${assets.length}张)</span>
            <button class="btn-sm fetch-assets-btn" data-id="${s.id}" ${_busyOps[s.id]?.has("fetch") ? "disabled" : ""}>${_busyOps[s.id]?.has("fetch") ? "抓取中…" : "抓取"}</button>
          </div>
          ${assets.length ? `<div class="asset-thumbs">${assets.map(a => {
            const localSrc = a.local ? `/${a.local}` : esc(a.url);
            return `<div class="asset-thumb-wrap lb-trigger" data-url="${localSrc}" data-caption="${esc(a.caption || a.keyword || '')}">
              <img src="${localSrc}" onerror="this.parentElement.style.display='none'">
              <div class="asset-caption">${esc(a.caption || a.keyword || '')}</div>
            </div>`;
          }).join("")}</div>` : ""}
        </div>
        <div class="cover-col">
          ${coverSrc ? `<div class="asset-thumb-wrap lb-trigger cover-thumb" data-url="${coverSrc}" data-caption="封面">
            <img class="cover-preview-img" data-id="${s.id}" src="${coverSrc}" onerror="this.closest('.cover-thumb').style.display='none'">
            <div class="asset-caption">封面</div>
          </div>` : `<div class="cover-thumb-placeholder"></div>`}
          <button class="btn-sm gen-cover-btn" data-id="${s.id}" ${_busyOps[s.id]?.has("cover") ? "disabled" : ""}>${_busyOps[s.id]?.has("cover") ? "生成中…" : "生成封面"}</button>
        </div>
      </div>
      <div class="produce-step ${hasAudio ? 'done' : ''}">
        <span class="step-icon">${hasAudio ? "✓" : "○"}</span>
        <span>配音</span>
        <button class="btn-sm gen-audio-btn" data-id="${s.id}" ${_busyOps[s.id]?.has("audio") ? "disabled" : ""}>${_busyOps[s.id]?.has("audio") ? "配音中…" : "生成配音"}</button>
        <button class="btn-sm tts-settings-btn" title="TTS参数设置">⚙</button>
        ${hasAudio ? `<audio controls preload="none" style="width:100%;margin-top:4px;height:32px"><source src="/data/stories/${s.id}/audio.mp3?t=${s.updated_at||s.id}" type="audio/mpeg"></audio>` : ""}
      </div>
      <div class="produce-step ${hasVideo ? 'done' : ''}">
        <span class="step-icon">${hasVideo ? "✓" : "○"}</span>
        <span>视频</span>
        <button class="btn-sm render-video-btn" data-id="${s.id}" ${(!hasAudio || _busyOps[s.id]?.has("video")) ? "disabled" : ""}>${_busyOps[s.id]?.has("video") ? "合成中…" : "合成视频"}</button>
        ${hasVideo ? `<a class="btn-sm btn-primary" href="/${s.video_path}" target="_blank">下载</a>` : ""}
        ${hasVideo ? `<button class="btn-sm play-video-btn" data-src="/${s.video_path}">▶ 预览</button>` : ""}
      </div>
    </div>`;
  }

  // 抖音链接
  if (["done","published"].includes(s.status)) {
    content += `
    <div class="douyin-row">
      <input type="text" placeholder="粘贴抖音链接…" class="douyin-input" value="${esc(s.douyin_url || "")}">
      <button class="btn-sm btn-primary save-douyin-btn" data-id="${s.id}">标记发布</button>
    </div>`;
  }

  // 失败信息
  if (s.status === "failed" && s.error_msg) {
    content += `<div class="error-box">⚠️ ${esc(s.error_msg)}</div>`;
  }

  // 操作按钮
  const actions = [];
  if (s.status === "pending_research")
    actions.push(`<button class="btn-sm btn-primary research-btn" data-id="${s.id}">开始研究</button>`);
  if (s.status === "researching")
    actions.push(`<span style="font-size:12px;color:var(--blue)">研究中…</span>`);
  if (s.status === "research_done")
    actions.push(`<span style="font-size:12px;color:var(--blue)">研究完成，生成脚本中…</span>`);
  if (s.status === "scripting")
    actions.push(`<span style="font-size:12px;color:var(--orange)">生成中…</span>`);
  if (s.status === "script_draft")
    actions.push(`<button class="btn-sm btn-primary edit-script-btn" data-id="${s.id}">编辑 / 审核</button>`);
  if (s.status === "script_approved")
    actions.push(`<button class="btn-sm edit-script-btn" data-id="${s.id}">查看脚本</button>`);

  if (s.status === "failed")
    actions.push(`<button class="btn-sm btn-primary retry-discover-btn" data-id="${s.id}" data-book-id="${s.book_id}">重试</button>`);
  actions.push(`<button class="btn-sm btn-danger del-story-btn" data-id="${s.id}">删除</button>`);

  return `
  <div class="story-card" id="story-card-${s.id}" data-id="${s.id}">
    <div class="story-card-top">
      <div>
        <div class="story-title">${esc(s.angle)}</div>
        <div class="story-book-name">《${esc(s.book_title)}》${s.book_author ? `· ${esc(s.book_author)}` : ""}</div>
      </div>
      <span class="status-badge status-${s.status}">${STATUS_LABEL[s.status] || s.status}</span>
    </div>
    ${content}
    <div class="story-actions">${actions.join("")}</div>
  </div>`;
}

function attachStoryEvents(root = document) {
  const $ = sel => root.querySelectorAll(sel);
  root.querySelectorAll(".research-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true; btn.textContent = "研究中…";
      try {
        await post(`/stories/${btn.dataset.id}/research`, {});
        toast("研究任务已启动");
      } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "开始研究"; }
    });
  });

  $(".gen-script-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true; btn.textContent = "生成中…";
      try {
        await post(`/stories/${btn.dataset.id}/generate-script`, {});
        toast("脚本生成中…");
      } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "生成脚本"; }
    });
  });

  $(".edit-script-btn, .view-script-btn").forEach(btn => {
    btn.addEventListener("click", () => openScriptModal(btn.dataset.id));
  });

  $(".fetch-assets-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      if (!_busyOps[id]) _busyOps[id] = new Set();
      _busyOps[id].add("fetch");
      btn.disabled = true; btn.textContent = "抓取中…";
      try {
        await post(`/stories/${id}/fetch-assets`, {});
        toast("素材抓取中，约30秒后刷新");
        // 服务端抓取开始时立即清空 assets，所以 baseline 固定为 -1
        // 只要 assets.length > -1（即 >= 0 且不为空，或抓取完成）就停止
        const poll = setInterval(async () => {
          try {
            const s = await get(`/stories/${id}`);
            let assets = []; try { assets = JSON.parse(s.assets || "[]"); } catch {}
            if (assets.length > 0 || s.status === "failed") {
              clearInterval(poll);
              _busyOps[id]?.delete("fetch");
              patchStoryCard(s);
            }
          } catch (_) { clearInterval(poll); _busyOps[id]?.delete("fetch"); }
        }, 4000);
        setTimeout(() => { clearInterval(poll); _busyOps[id]?.delete("fetch"); }, 120000);
      } catch (e) {
        toast(e.message, true);
        _busyOps[id]?.delete("fetch");
        btn.disabled = false; btn.textContent = "抓取";
      }
    });
  });

  $(".gen-cover-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      if (!_busyOps[id]) _busyOps[id] = new Set();
      _busyOps[id].add("cover");
      btn.disabled = true; btn.textContent = "生成中…";
      try {
        await post(`/stories/${id}/generate-cover`, {});
        toast("封面生成中…");
        const poll = setInterval(async () => {
          try {
            const story = (await get(`/stories/${id}`));
            if (story?.cover_path) {
              clearInterval(poll);
              _busyOps[id]?.delete("cover");
              btn.disabled = false; btn.textContent = "生成封面✓";
              toast("封面已生成");
              // 刷新封面预览
              const ts = Date.now();
              const newSrc = `/${story.cover_path}?t=${ts}`;
              const img = document.querySelector(`.cover-preview-img[data-id="${id}"]`);
              if (img) {
                img.src = newSrc;
                const wrap = img.closest(".cover-thumb");
                if (wrap) { wrap.dataset.url = newSrc; wrap.style.display = ""; }
              } else {
                // 重新渲染卡片以显示封面
                patchStoryCard(story);
              }
            }
          } catch (_) { clearInterval(poll); _busyOps[id]?.delete("cover"); }
        }, 3000);
        setTimeout(() => { clearInterval(poll); _busyOps[id]?.delete("cover"); }, 30000);
      } catch (e) {
        toast(e.message, true);
        _busyOps[id]?.delete("cover");
        btn.disabled = false; btn.textContent = "生成封面";
      }
    });
  });

  $(".gen-audio-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      if (!_busyOps[id]) _busyOps[id] = new Set();
      _busyOps[id].add("audio");
      btn.disabled = true; btn.textContent = "配音中…";
      try {
        await post(`/stories/${id}/generate-audio`, {});
        toast("TTS配音任务已启动");
        setTimeout(() => { _busyOps[id]?.delete("audio"); }, 180000); // safety
      } catch (e) {
        toast(e.message, true);
        _busyOps[id]?.delete("audio");
        btn.disabled = false; btn.textContent = "生成配音";
      }
    });
  });

  $(".play-video-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const player = document.getElementById("video-player");
      player.src = btn.dataset.src;
      player.load();
      player.play().catch(() => {});
      document.getElementById("video-modal").classList.remove("hidden");
    });
  });

  $(".render-video-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      if (!_busyOps[id]) _busyOps[id] = new Set();
      _busyOps[id].add("video");
      btn.disabled = true; btn.textContent = "合成中…";
      try {
        await post(`/stories/${id}/render-video`, {});
        toast("视频合成任务已启动");
        setTimeout(() => { _busyOps[id]?.delete("video"); }, 600000); // safety
      } catch (e) {
        toast(e.message, true);
        _busyOps[id]?.delete("video");
        btn.disabled = false; btn.textContent = "合成视频";
      }
    });
  });

  $(".save-douyin-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const input = btn.previousElementSibling;
      try {
        await api("PATCH", `/stories/${btn.dataset.id}/douyin`, { douyin_url: input.value.trim() });
        toast("已标记为已发布");
        loadStories();
      } catch (e) { toast(e.message, true); }
    });
  });

  $(".retry-discover-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true; btn.textContent = "重试中…";
      try {
        await del(`/stories/${btn.dataset.id}`);
        await post(`/books/${btn.dataset.bookId}/discover-story`, {});
        toast("已重新触发，约3分钟后刷新");
        setTimeout(loadStories, 2000);
      } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "重试"; }
    });
  });

  $(".del-story-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm("确认删除？")) return;
      try {
        await del(`/stories/${btn.dataset.id}`);
        toast("已删除");
        loadStories();
      } catch (e) { toast(e.message, true); }
    });
  });
}

// ── 脚本编辑弹窗 ──────────────────────────────────────────────────────────────
let _currentStoryId = null;

async function openScriptModal(storyId) {
  _currentStoryId = storyId;
  const story = await get(`/stories/${storyId}`);
  document.getElementById("script-modal-title").textContent = `${story.angle} · 《${story.book_title}》`;
  document.getElementById("script-editor").value = story.script || "";
  updateWordCount();

  const sumEl = document.getElementById("script-research-summary");
  if (story.research_summary) {
    try {
      const s = JSON.parse(story.research_summary);
      sumEl.innerHTML = (s.facts || []).slice(0, 3).map(f => `· ${esc(f)}`).join("<br>");
      sumEl.classList.remove("hidden");
    } catch { sumEl.classList.add("hidden"); }
  } else {
    sumEl.classList.add("hidden");
  }

  // 已审核/完成状态隐藏「审核通过」按钮，只保留「重新生成」
  const isDraft = story.status === "script_draft";
  document.getElementById("btn-approve-script").style.display = isDraft ? "" : "none";

  document.getElementById("script-modal").classList.remove("hidden");
}

function closeScriptModal() {
  document.getElementById("script-modal").classList.add("hidden");
  _currentStoryId = null;
}

function updateWordCount() {
  const text = document.getElementById("script-editor").value;
  const wc = text.length, sec = Math.round(wc / 4.5);
  const color = wc < 120 ? "var(--red)" : wc > 250 ? "var(--orange)" : "var(--green)";
  document.getElementById("script-word-count").innerHTML =
    `<span style="color:${color};font-weight:600">${wc}字</span> · 约${sec}秒`;
}

document.getElementById("script-editor").addEventListener("input", updateWordCount);

document.getElementById("btn-approve-script").addEventListener("click", async () => {
  if (!_currentStoryId) return;
  const script = document.getElementById("script-editor").value.trim();
  if (!script) { toast("脚本内容不能为空", true); return; }
  const btn = document.getElementById("btn-approve-script");
  btn.disabled = true;
  try {
    await post(`/stories/${_currentStoryId}/approve-script`, { script });
    toast("审核通过，可以开始制作了");
    closeScriptModal();
    loadStories();
  } catch (e) { toast(e.message, true); }
  btn.disabled = false;
});

document.getElementById("btn-regen-script").addEventListener("click", async () => {
  if (!_currentStoryId) return;
  const storyId = _currentStoryId;
  const btn = document.getElementById("btn-regen-script");
  btn.disabled = true; btn.textContent = "生成中…";
  try {
    await post(`/stories/${storyId}/generate-script`, {});
    toast("重新生成中，约30秒后自动更新…");
    closeScriptModal();
    // 轮询直到状态变回 script_draft
    const poll = setInterval(async () => {
      const s = await get(`/stories/${storyId}`);
      patchStoryCard(s);
      if (s.status === "script_draft") {
        clearInterval(poll);
        openScriptModal(storyId);
      }
    }, 3000);
  } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "重新生成"; }
});

document.getElementById("script-modal").addEventListener("click", e => {
  if (e.target === document.getElementById("script-modal")) closeScriptModal();
});

// ── 轮询：逐卡片 diff，只替换有变化的卡片 ────────────────────────────────────
const IN_PROGRESS_STATUSES = new Set(["pending_research","researching","scripting","producing"]);
let _lastStoryStatuses = {}; // { id: status }
// 记录正在进行的操作 { storyId: Set<"fetch"|"audio"|"video"> }
const _busyOps = {};

function isMediaPlaying() {
  return [...document.querySelectorAll("audio, video")].some(m => !m.paused);
}

function patchStoryCard(s) {
  const existing = document.getElementById(`story-card-${s.id}`);
  const tmp = document.createElement("div");
  tmp.innerHTML = renderStoryCard(s);
  const newCard = tmp.firstElementChild;
  if (existing) {
    existing.replaceWith(newCard);
  } else {
    document.getElementById("story-list").insertAdjacentElement("afterbegin", newCard);
  }
  attachStoryEvents(newCard);
}

setInterval(async () => {
  const hasBusyOps = Object.values(_busyOps).some(s => s?.size > 0);
  const hasActive = Object.values(_lastStoryStatuses).some(st => IN_PROGRESS_STATUSES.has(st));
  if (!hasActive && !hasBusyOps) return;

  try {
    const status = document.getElementById("story-filter").value;
    let url = "/stories";
    const params = [];
    if (_selectedBookId) params.push(`book_id=${_selectedBookId}`);
    if (status) params.push(`status=${status}`);
    if (params.length) url += "?" + params.join("&");

    const stories = await get(url);
    let todayNeedsUpdate = false;
    for (const s of stories) {
      // Detect busy-op completions and clear them
      let opsCleared = false;
      if (_busyOps[s.id]?.has("audio") && s.audio_path) {
        _busyOps[s.id].delete("audio"); opsCleared = true;
      }
      if (_busyOps[s.id]?.has("video") && (s.video_path || s.status === "done")) {
        _busyOps[s.id].delete("video"); opsCleared = true;
      }
      if (_busyOps[s.id]?.has("fetch")) {
        let assets = []; try { assets = JSON.parse(s.assets || "[]"); } catch {}
        if (assets.length > 0) {
          _busyOps[s.id].delete("fetch");
          opsCleared = true;
        }
      }
      // Also clear busy ops on failure so button doesn't stay stuck
      if (s.status === "failed") {
        if (_busyOps[s.id]?.has("audio")) { _busyOps[s.id].delete("audio"); opsCleared = true; }
        if (_busyOps[s.id]?.has("video")) { _busyOps[s.id].delete("video"); opsCleared = true; }
      }

      const statusChanged = _lastStoryStatuses[s.id] !== s.status;
      if (statusChanged || opsCleared) {
        if (!isMediaPlaying() || !document.getElementById(`story-card-${s.id}`)?.querySelector("audio,video[src]")) {
          patchStoryCard(s);
          _lastStoryStatuses[s.id] = s.status;
          todayNeedsUpdate = true;
        }
      }
    }
    if (todayNeedsUpdate) loadTodayPanel();
  } catch (_) {}
}, 5000);

// ── 图片 Lightbox ─────────────────────────────────────────────────────────────
document.addEventListener("click", e => {
  const t = e.target.closest(".lb-trigger");
  if (t) openLightbox(t.dataset.url, t.dataset.caption);
});

function openLightbox(url, caption) {
  let box = document.getElementById("lightbox");
  if (!box) {
    box = document.createElement("div");
    box.id = "lightbox";
    box.innerHTML = `
      <div class="lb-backdrop" onclick="closeLightbox()"></div>
      <div class="lb-box">
        <img id="lb-img" src="">
        <div id="lb-caption"></div>
        <button class="lb-close" onclick="closeLightbox()">✕</button>
      </div>`;
    document.body.appendChild(box);
  }
  document.getElementById("lb-img").src = url;
  document.getElementById("lb-caption").textContent = caption;
  box.classList.add("lb-show");
}
function closeLightbox() {
  document.getElementById("lightbox")?.classList.remove("lb-show");
}
document.addEventListener("keydown", e => { if (e.key === "Escape") closeLightbox(); });

// ── TTS 设置弹窗 ──────────────────────────────────────────────────────────────
document.addEventListener("click", e => {
  if (e.target.closest(".tts-settings-btn")) openTtsSettings();
});

async function openTtsSettings() {
  let box = document.getElementById("tts-settings-modal");
  if (!box) {
    box = document.createElement("div");
    box.id = "tts-settings-modal";
    box.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;align-items:center;justify-content:center";
    box.innerHTML = `
      <div style="background:var(--card-bg,#1e2130);border-radius:14px;padding:28px 32px;min-width:320px;color:var(--text,#eee)">
        <div style="font-size:15px;font-weight:600;margin-bottom:20px">TTS 配音参数</div>
        ${ttsSlider("speed_ratio",  "语速",     0.5, 1.5, 0.01, "慢 ←→ 快")}
        ${ttsSlider("pitch_ratio",  "音调",     0.8, 1.2, 0.01, "低沉 ←→ 高亮")}
        ${ttsSlider("volume_ratio", "音量",     0.5, 2.0, 0.05, "")}
        ${ttsSlider("silence_s",    "句间停顿", 0,   2.0, 0.1,  "秒")}
        <div style="display:flex;gap:10px;margin-top:22px;justify-content:flex-end">
          <button class="btn-sm" id="tts-cancel-btn">取消</button>
          <button class="btn-sm btn-primary" id="tts-save-btn">保存</button>
        </div>
      </div>`;
    document.body.appendChild(box);
    box.addEventListener("click", e => { if (e.target === box) box.remove(); });
    document.getElementById("tts-cancel-btn").addEventListener("click", () => box.remove());
    document.getElementById("tts-save-btn").addEventListener("click", saveTtsSettings);
    box.querySelectorAll("input[type=range]").forEach(r => {
      r.addEventListener("input", () => {
        document.getElementById("tts-val-" + r.name).textContent = r.value;
      });
    });
  }
  try {
    const s = await get("/tts-settings");
    ["speed_ratio","pitch_ratio","volume_ratio","silence_s"].forEach(k => {
      const r = box.querySelector(`input[name="${k}"]`);
      if (r) { r.value = s[k]; document.getElementById("tts-val-" + k).textContent = s[k]; }
    });
  } catch(_) {}
  document.body.appendChild(box);
}

function ttsSlider(name, label, min, max, step, hint) {
  return `<div style="margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
      <span>${label}${hint ? ` <span style="opacity:.5;font-size:11px">${hint}</span>` : ""}</span>
      <span id="tts-val-${name}" style="font-weight:600;min-width:36px;text-align:right">—</span>
    </div>
    <input type="range" name="${name}" min="${min}" max="${max}" step="${step}"
      style="width:100%;accent-color:var(--blue,#4a9eff)">
  </div>`;
}

async function saveTtsSettings() {
  const box = document.getElementById("tts-settings-modal");
  const body = {};
  box.querySelectorAll("input[type=range]").forEach(r => { body[r.name] = parseFloat(r.value); });
  try {
    await post("/tts-settings", body);
    toast("TTS参数已保存");
    box.remove();
  } catch(e) { toast(e.message, true); }
}

// ── 初始化 ────────────────────────────────────────────────────────────────────
loadTodayPanel();
loadBooks();
loadStories();
