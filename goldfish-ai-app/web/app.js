const chatEl = document.getElementById("chat");
const formEl = document.getElementById("ask-form");
const qEl = document.getElementById("question");
const topkEl = document.getElementById("topk");

function appendBubble(kind, text) {
  const tpl = document.getElementById(kind === "user" ? "bubble-user" : "bubble-ai");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".content").textContent = text;
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function renderAnswer(resp) {
  const lines = [];
  lines.push(`結論: ${resp.conclusion}`);
  lines.push(`信心: ${Number(resp.confidence || 0).toFixed(2)}`);
  lines.push("依據:");
  resp.evidence.forEach((item, i) => lines.push(`- [${i + 1}] ${item}`));
  lines.push("來源:");

  if (!resp.sources.length) {
    lines.push("- 無");
  } else {
    resp.sources.forEach((s, i) => {
      lines.push(`- [來源 ${i + 1}] ${s.title} / ${s.section}`);
      lines.push(`  URL: ${s.url}`);
    });
  }

  return lines.join("\n");
}

async function sendFeedback(interactionId, rating, comment = "") {
  const res = await fetch("/api/feedback", {
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
  const res = await fetch("/api/ask", {
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
    appendBubble("ai", renderAnswer(answer));
    appendFeedbackControls(answer.interaction_id);
  } catch (err) {
    appendBubble("ai", "系統暫時無法回應，請稍後再試。\n" + String(err));
  } finally {
    button.disabled = false;
  }
});

appendBubble("ai", "你好，我是 Goldfish AI。\n請輸入金魚飼養問題，我會附上來源。\n");
