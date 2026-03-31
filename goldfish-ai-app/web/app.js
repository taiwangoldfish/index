const chatEl = document.getElementById("chat");
const formEl = document.getElementById("ask-form");
const qEl = document.getElementById("question");
const topkEl = document.getElementById("topk");
const API_BASE = (window.GOLDFISH_API_BASE || "").replace(/\/$/, "");

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function appendBubble(kind, text, isHtml = false) {
  const tpl = document.getElementById(kind === "user" ? "bubble-user" : "bubble-ai");
  const node = tpl.content.firstElementChild.cloneNode(true);
  const contentEl = node.querySelector(".content");
  if (isHtml) {
    contentEl.innerHTML = text;
  } else {
    contentEl.textContent = text;
  }
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderAnswer(resp) {
  const conf = Number(resp.confidence || 0);
  const confColor = conf >= 0.6 ? '#27ae60' : conf >= 0.35 ? '#e67e22' : '#e74c3c';
  const confLabel = conf >= 0.6 ? '高' : conf >= 0.35 ? '中' : '低';

  let html = `<div class="ans-conclusion">${escapeHtml(resp.conclusion)}</div>`;
  html += `<div class="ans-conf">信心：<span style="color:${confColor};font-weight:600">${confLabel}（${conf.toFixed(2)}）</span></div>`;

  if (resp.matched_keywords && resp.matched_keywords.length) {
    const total = Number(resp.matched_keywords_total || resp.matched_keywords.length);
    const shown = resp.matched_keywords.slice(0, 12);
    const more = total > shown.length ? ` 等 ${total} 個` : '';
    html += `<div class="ans-kw"><strong>辨識關鍵字（共 ${total} 個）：</strong>${shown.map(escapeHtml).join('、')}${more}</div>`;
  }

  if (resp.evidence && resp.evidence.length) {
    html += `<div class="ans-evidence"><strong>相關段落（搜尋結果）：</strong><ol>`;
    resp.evidence.forEach((line) => {
      html += `<li>${escapeHtml(line)}</li>`;
    });
    html += `</ol></div>`;
  }

  if (resp.sources && resp.sources.length) {
    html += `<div class="ans-sources"><strong>參考來源：</strong><ul>`;
    resp.sources.forEach((s, idx) => {
      const shortUrl = s.url.replace('https://taiwangoldfish.github.io/','');
      html += `<li>[來源 ${idx + 1}] <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(shortUrl)}</a></li>`;
    });
    html += `</ul></div>`;
  }

  return html;
}

async function sendFeedback(interactionId, rating, comment = "") {
  const res = await fetch(apiUrl("/api/feedback"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interaction_id: interactionId, rating, comment }),
  });
  if (!res.ok) {
    throw new Error(`Feedback API error: ${res.status}`);
  }
}

function appendFeedbackControls(interactionId) {
  if (!interactionId) return;
  const wrap = document.createElement("div");
  wrap.className = "feedback";

  const upBtn = document.createElement("button");
  upBtn.type = "button";
  upBtn.textContent = "👍 有幫助";

  const downBtn = document.createElement("button");
  downBtn.type = "button";
  downBtn.textContent = "👎 不精準";

  const status = document.createElement("span");
  status.className = "feedback-status";

  async function submit(rating) {
    upBtn.disabled = true;
    downBtn.disabled = true;
    try {
      await sendFeedback(interactionId, rating);
      status.textContent = "已收到回饋";
    } catch (err) {
      status.textContent = "回饋送出失敗";
      upBtn.disabled = false;
      downBtn.disabled = false;
    }
  }

  upBtn.addEventListener("click", () => submit("up"));
  downBtn.addEventListener("click", () => submit("down"));

  wrap.appendChild(upBtn);
  wrap.appendChild(downBtn);
  wrap.appendChild(status);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
}

async function askQuestion(question, topK) {
  const res = await fetch(apiUrl("/api/ask"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = qEl.value.trim();
  if (!question) return;

  const topK = Number(topkEl.value || 5);
  const button = formEl.querySelector("button");

  appendBubble("user", question);
  qEl.value = "";

  button.disabled = true;
  try {
    const answer = await askQuestion(question, topK);
    appendBubble("ai", renderAnswer(answer), true);
    appendFeedbackControls(answer.interaction_id);
  } catch (err) {
    appendBubble("ai", "系統暫時無法回應，請稍後再試。\n" + String(err));
  } finally {
    button.disabled = false;
  }
});

// Enter to submit, Shift+Enter for newline
qEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});

appendBubble("ai", "你好，我是 Goldfish AI。\n請輸入金魚飼養問題，我會附上來源。");
