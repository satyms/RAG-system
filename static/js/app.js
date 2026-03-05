/* ================================================================
   RAG System - UI logic (Phase 4: Advanced Intelligence Layer)
   ================================================================ */

const API = "";

// -- Views -------------------------------------------------------
const heroView  = document.getElementById("heroView");
const chatView  = document.getElementById("chatView");

// -- Hero inputs -------------------------------------------------
const heroInput   = document.getElementById("heroInput");
const heroSendBtn = document.getElementById("heroSendBtn");
const fileInput   = document.getElementById("fileInput");
const uploadPill  = document.getElementById("uploadPill");
const uploadChip  = document.getElementById("uploadChip");
const healthChip  = document.getElementById("healthChip");
const clearChip   = document.getElementById("clearChip");

// -- Chat view ---------------------------------------------------
const chatMessages = document.getElementById("chatMessages");
const chatInput    = document.getElementById("chatInput");
const chatSendBtn  = document.getElementById("chatSendBtn");
const newChatBtn   = document.getElementById("newChatBtn");
const fileInputNav = document.getElementById("fileInputNav");
const fileInputBar = document.getElementById("fileInputBar");

// -- Phase 4 toggles --------------------------------------------
const agentToggle = document.getElementById("agentToggle");
const debugToggle = document.getElementById("debugToggle");

// -- State -------------------------------------------------------
let busy = false;

/* ================================================================
   HERO VIEW LOGIC
   ================================================================ */

heroInput.addEventListener("input", () => {
  heroInput.style.height = "auto";
  heroInput.style.height = Math.min(heroInput.scrollHeight, 160) + "px";
  heroSendBtn.disabled = !heroInput.value.trim();
});

heroInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!heroSendBtn.disabled) submitHeroQuery();
  }
});

heroSendBtn.addEventListener("click", submitHeroQuery);

function submitHeroQuery() {
  const q = heroInput.value.trim();
  if (!q) return;
  switchToChat();
  sendQuery(q);
  heroInput.value = "";
  heroInput.style.height = "auto";
  heroSendBtn.disabled = true;
}

// Quick action chips
document.querySelectorAll(".chip[data-q]").forEach(chip => {
  chip.addEventListener("click", () => {
    const q = chip.dataset.q;
    if (!q) return;
    switchToChat();
    sendQuery(q);
  });
});

uploadChip.addEventListener("click", () => fileInput.click());

healthChip.addEventListener("click", async () => {
  switchToChat();
  const typing = showTyping();
  try {
    const res  = await fetch(`${API}/api/health`);
    const data = await res.json();
    removeTyping(typing);
    appendMsg("assistant", `System Status\n\nStatus: ${data.status || "OK"}\n${JSON.stringify(data, null, 2)}`);
  } catch (err) {
    removeTyping(typing);
    appendMsg("assistant", `Could not reach health endpoint: ${err.message}`);
  }
});

clearChip.addEventListener("click", resetToHero);

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleUpload(fileInput.files[0], uploadPill);
});

/* ================================================================
   CHAT VIEW LOGIC
   ================================================================ */

[fileInputNav, fileInputBar].forEach(el => {
  el.addEventListener("change", () => {
    if (el.files.length) handleUpload(el.files[0]);
    el.value = "";
  });
});

chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
  chatSendBtn.disabled = !chatInput.value.trim();
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!chatSendBtn.disabled && !busy) submitChatQuery();
  }
});

chatSendBtn.addEventListener("click", () => {
  if (!busy) submitChatQuery();
});

function submitChatQuery() {
  const q = chatInput.value.trim();
  if (!q) return;
  chatInput.value = "";
  chatInput.style.height = "auto";
  chatSendBtn.disabled = true;
  sendQuery(q);
}

newChatBtn.addEventListener("click", resetToHero);

/* ================================================================
   CORE LOGIC
   ================================================================ */

function switchToChat() {
  heroView.hidden = true;
  chatView.hidden = false;
}

function resetToHero() {
  chatMessages.innerHTML = "";
  chatView.hidden = true;
  heroView.hidden = false;
  busy = false;
}

async function sendQuery(question) {
  if (busy) return;
  busy = true;

  appendMsg("user", question);
  const typing = showTyping();

  const useAgents = agentToggle ? agentToggle.checked : false;
  const showDebug = debugToggle ? debugToggle.checked : false;

  try {
    const res = await fetch(`${API}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        use_agents: useAgents,
        debug: showDebug,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Query failed");

    removeTyping(typing);

    const msgEl = appendMsg("assistant", data.answer, data.sources);

    // Phase 4: metadata badges
    renderMetaBadges(msgEl, data);

    // Phase 4: feedback buttons
    renderFeedback(msgEl, question, data.answer);

    // Phase 4: debug panel
    if (showDebug && data.debug) {
      renderDebugPanel(msgEl, data.debug);
    }

  } catch (err) {
    removeTyping(typing);
    appendMsg("assistant", `Error: ${err.message}`);
  }

  busy = false;
}

async function handleUpload(file, statusEl) {
  const pill = statusEl || null;

  if (pill) {
    pill.textContent = `Uploading ${file.name}...`;
    pill.className = "upload-pill";
    pill.hidden = false;
  } else {
    appendMsg("assistant", `Uploading ${file.name}...`);
  }

  const fd = new FormData();
  fd.append("file", file);

  try {
    const res  = await fetch(`${API}/api/ingest`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    const msg = `${data.filename} - ${data.chunks} chunks indexed`;
    if (pill) {
      pill.textContent = msg;
      pill.className = "upload-pill success";
    } else {
      appendMsg("assistant", msg);
    }
  } catch (err) {
    const msg = `Upload failed: ${err.message}`;
    if (pill) {
      pill.textContent = msg;
      pill.className = "upload-pill error";
    } else {
      appendMsg("assistant", msg);
    }
  }
}

/* ================================================================
   HELPERS
   ================================================================ */

function appendMsg(role, text, sources) {
  sources = sources || [];
  const div = document.createElement("div");
  div.className = `msg ${role}`;

  const label = document.createElement("span");
  label.className = "role-label";
  label.textContent = role === "user" ? "You" : "RAG System";
  div.appendChild(label);

  const body = document.createElement("span");
  body.textContent = text;
  div.appendChild(body);

  // Sources accordion
  if (sources.length) {
    const btn = document.createElement("button");
    btn.className = "sources-toggle";
    btn.innerHTML = `<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' width='13' height='13'><path d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/><path d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/></svg> ${sources.length} source(s)`;
    div.appendChild(btn);

    const list = document.createElement("div");
    list.className = "sources-list";
    sources.forEach((s, i) => {
      const row = document.createElement("p");
      row.textContent = `[${i + 1}] ${s.source || "unknown"} (score: ${s.score != null ? s.score.toFixed(4) : "n/a"})`;
      list.appendChild(row);

      const snippet = document.createElement("p");
      snippet.style.cssText = "opacity:.6;margin-bottom:8px;font-size:.74rem;";
      snippet.textContent = (s.content || "").slice(0, 220) + ((s.content && s.content.length > 220) ? "..." : "");
      list.appendChild(snippet);
    });
    div.appendChild(list);
    btn.addEventListener("click", () => list.classList.toggle("open"));
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = "<span></span><span></span><span></span>";
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function removeTyping(el) { if (el) el.remove(); }

/* ================================================================
   PHASE 4: METADATA BADGES
   ================================================================ */

function renderMetaBadges(msgEl, data) {
  const wrap = document.createElement("div");
  wrap.className = "meta-badges";

  // Confidence
  if (data.confidence_score != null) {
    const b = badge(
      `Confidence: ${(data.confidence_score * 100).toFixed(1)}%`,
      data.confidence_score >= 0.7 ? "green" : data.confidence_score >= 0.4 ? "yellow" : "red"
    );
    wrap.appendChild(b);
  }

  // Faithfulness
  if (data.faithfulness_score != null) {
    const b = badge(
      `Faithfulness: ${(data.faithfulness_score * 100).toFixed(1)}%`,
      data.faithfulness_score >= 0.7 ? "green" : data.faithfulness_score >= 0.4 ? "yellow" : "red"
    );
    wrap.appendChild(b);
  }

  // Grounded
  if (data.is_grounded && data.is_grounded !== "unknown") {
    wrap.appendChild(badge(`Grounded: ${data.is_grounded}`, data.is_grounded === "yes" ? "green" : "red"));
  }

  // Latency
  if (data.latency_ms) {
    wrap.appendChild(badge(`${data.latency_ms}ms`, "neutral"));
  }

  // Agent metadata
  const am = data.agent_metadata || {};
  if (am.intent) {
    wrap.appendChild(badge(`Intent: ${am.intent}`, "blue"));
  }
  if (am.complexity) {
    wrap.appendChild(badge(`Complexity: ${am.complexity}`, "blue"));
  }
  if (am.requires_human_review) {
    wrap.appendChild(badge("Needs Review", "red"));
  }

  if (wrap.children.length) {
    msgEl.appendChild(wrap);
  }
}

function badge(text, color) {
  const s = document.createElement("span");
  s.className = `badge badge-${color}`;
  s.textContent = text;
  return s;
}

/* ================================================================
   PHASE 4: FEEDBACK BUTTONS
   ================================================================ */

function renderFeedback(msgEl, query, answer) {
  const wrap = document.createElement("div");
  wrap.className = "feedback-row";

  const upBtn = document.createElement("button");
  upBtn.className = "feedback-btn";
  upBtn.title = "Good answer";
  upBtn.innerHTML = `<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' width='14' height='14'><path d='M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z'/><path d='M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'/></svg>`;

  const downBtn = document.createElement("button");
  downBtn.className = "feedback-btn";
  downBtn.title = "Bad answer";
  downBtn.innerHTML = `<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' width='14' height='14'><path d='M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z'/><path d='M17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3'/></svg>`;

  upBtn.addEventListener("click", () => submitFeedback(query, answer, "positive", wrap));
  downBtn.addEventListener("click", () => submitFeedback(query, answer, "negative", wrap));

  wrap.appendChild(upBtn);
  wrap.appendChild(downBtn);
  msgEl.appendChild(wrap);
}

async function submitFeedback(query, answer, rating, wrap) {
  wrap.innerHTML = '<span class="feedback-thanks">Sending...</span>';
  try {
    const res = await fetch(`${API}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, answer, rating }),
    });
    if (!res.ok) throw new Error("Failed");
    wrap.innerHTML = '<span class="feedback-thanks">Thanks for your feedback!</span>';
  } catch {
    wrap.innerHTML = '<span class="feedback-thanks">Could not save feedback</span>';
  }
}

/* ================================================================
   PHASE 4: DEBUG PANEL
   ================================================================ */

function renderDebugPanel(msgEl, debugData) {
  const details = document.createElement("details");
  details.className = "debug-panel";

  const summary = document.createElement("summary");
  summary.textContent = "Debug Info";
  details.appendChild(summary);

  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(debugData, null, 2);
  details.appendChild(pre);

  msgEl.appendChild(details);
}

