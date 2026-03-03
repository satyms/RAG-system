/* ═══════════════════════════════════════════════════════════
   RAG System — Ruixen-style UI logic
   ═══════════════════════════════════════════════════════════ */

const API = "";

// ── Views ────────────────────────────────────────────────────
const heroView   = document.getElementById("heroView");
const chatView   = document.getElementById("chatView");

// ── Hero inputs ──────────────────────────────────────────────
const heroInput     = document.getElementById("heroInput");
const heroSendBtn   = document.getElementById("heroSendBtn");
const fileInput     = document.getElementById("fileInput");
const uploadPill    = document.getElementById("uploadPill");
const uploadChip    = document.getElementById("uploadChip");
const healthChip    = document.getElementById("healthChip");
const clearChip     = document.getElementById("clearChip");

// ── Chat view ────────────────────────────────────────────────
const chatMessages  = document.getElementById("chatMessages");
const chatInput     = document.getElementById("chatInput");
const chatSendBtn   = document.getElementById("chatSendBtn");
const newChatBtn    = document.getElementById("newChatBtn");
const fileInputNav  = document.getElementById("fileInputNav");
const fileInputBar  = document.getElementById("fileInputBar");

// ── State ─────────────────────────────────────────────────────
let busy = false;

// ═══════════════════════════════════════════════════════════
//  HERO VIEW LOGIC
// ═══════════════════════════════════════════════════════════

// Auto-resize hero textarea
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

// Upload chip triggers file input
uploadChip.addEventListener("click", () => fileInput.click());

// System health chip
healthChip.addEventListener("click", async () => {
  switchToChat();
  const typing = showTyping();
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();
    removeTyping(typing);
    appendMsg("assistant", `System Status\n\nStatus: ${data.status ?? "OK"}\n${JSON.stringify(data, null, 2)}`);
  } catch (err) {
    removeTyping(typing);
    appendMsg("assistant", `⚠ Could not reach health endpoint: ${err.message}`);
  }
});

// Clear chip
clearChip.addEventListener("click", resetToHero);

// Hero file upload
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleUpload(fileInput.files[0], uploadPill);
});

// ═══════════════════════════════════════════════════════════
//  CHAT VIEW LOGIC
// ═══════════════════════════════════════════════════════════

// Nav file uploads
[fileInputNav, fileInputBar].forEach(el => {
  el.addEventListener("change", () => {
    if (el.files.length) handleUpload(el.files[0]);
    el.value = "";
  });
});

// Chat textarea auto-resize
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

// New Chat button → back to hero
newChatBtn.addEventListener("click", resetToHero);

// ═══════════════════════════════════════════════════════════
//  CORE LOGIC
// ═══════════════════════════════════════════════════════════

function switchToChat() {
  heroView.hidden  = true;
  chatView.hidden  = false;
}

function resetToHero() {
  chatMessages.innerHTML = "";
  chatView.hidden  = true;
  heroView.hidden  = false;
  busy = false;
}

async function sendQuery(question) {
  if (busy) return;
  busy = true;

  appendMsg("user", question);
  const typing = showTyping();

  try {
    const res  = await fetch(`${API}/api/query`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Query failed");

    removeTyping(typing);
    appendMsg("assistant", data.answer, data.sources);
  } catch (err) {
    removeTyping(typing);
    appendMsg("assistant", `⚠ ${err.message}`);
  }

  busy = false;
}

async function handleUpload(file, statusEl) {
  const pill = statusEl || null;

  if (pill) {
    pill.textContent = `Uploading ${file.name}…`;
    pill.className   = "upload-pill";
    pill.hidden      = false;
  } else {
    appendMsg("assistant", `Uploading ${file.name}…`);
  }

  const fd = new FormData();
  fd.append("file", file);

  try {
    const res  = await fetch(`${API}/api/ingest`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    const msg = `✓ ${data.filename} — ${data.chunks} chunks indexed`;
    if (pill) {
      pill.textContent = msg;
      pill.className   = "upload-pill success";
    } else {
      appendMsg("assistant", msg);
    }
  } catch (err) {
    const msg = `✗ ${err.message}`;
    if (pill) {
      pill.textContent = msg;
      pill.className   = "upload-pill error";
    } else {
      appendMsg("assistant", msg);
    }
  }
}

// ── Helpers ─────────────────────────────────────────────────

function appendMsg(role, text, sources = []) {
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
  if (sources && sources.length) {
    const btn = document.createElement("button");
    btn.className = "sources-toggle";
    btn.innerHTML = `<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' width='13' height='13'><path d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/><path d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/></svg> ${sources.length} source(s)`;
    div.appendChild(btn);

    const list = document.createElement("div");
    list.className = "sources-list";
    sources.forEach((s, i) => {
      const row = document.createElement("p");
      row.textContent = `[${i + 1}] ${s.source || "unknown"} (score: ${s.score ?? "n/a"})`;
      list.appendChild(row);

      const snippet = document.createElement("p");
      snippet.style.cssText = "opacity:.6;margin-bottom:8px;font-size:.74rem;";
      snippet.textContent = (s.content || "").slice(0, 220) + ((s.content?.length > 220) ? "…" : "");
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
  div.innerHTML  = "<span></span><span></span><span></span>";
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function removeTyping(el) { el?.remove(); }

// ── DOM refs ────────────────────────────────────────────────
const messagesEl   = document.getElementById("messages");
const welcomeEl    = document.getElementById("welcome");
const chatForm     = document.getElementById("chatForm");
const userInput    = document.getElementById("userInput");
const sendBtn      = document.getElementById("sendBtn");
const fileInput    = document.getElementById("fileInput");
const uploadArea   = document.getElementById("uploadArea");
const uploadStatus = document.getElementById("uploadStatus");
const newChatBtn   = document.getElementById("newChatBtn");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebar       = document.getElementById("sidebar");

// ── State ───────────────────────────────────────────────────
let isGenerating = false;

// ── Auto-resize textarea ────────────────────────────────────
userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 150) + "px";
  sendBtn.disabled = !userInput.value.trim();
});

// Submit on Enter (Shift+Enter for new line)
userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled && !isGenerating) chatForm.requestSubmit();
  }
});

// ── Suggestion buttons ──────────────────────────────────────
document.querySelectorAll(".suggestion").forEach((btn) => {
  btn.addEventListener("click", () => {
    userInput.value = btn.dataset.q;
    userInput.dispatchEvent(new Event("input"));
    chatForm.requestSubmit();
  });
});

// ── New Chat ────────────────────────────────────────────────
newChatBtn.addEventListener("click", () => {
  messagesEl.innerHTML = "";
  messagesEl.appendChild(welcomeEl);
  welcomeEl.style.display = "";
  userInput.value = "";
  sendBtn.disabled = true;
});

// ── Mobile sidebar toggle ───────────────────────────────────
sidebarToggle.addEventListener("click", () => {
  sidebar.classList.toggle("open");
});

// ── File upload ─────────────────────────────────────────────
uploadArea.addEventListener("click", () => fileInput.click());

// Drag & drop
uploadArea.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadArea.style.borderColor = "var(--accent)";
});
uploadArea.addEventListener("dragleave", () => {
  uploadArea.style.borderColor = "";
});
uploadArea.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadArea.style.borderColor = "";
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFileUpload(fileInput.files[0]);
});

async function handleFileUpload(file) {
  uploadStatus.textContent = `Uploading ${file.name}…`;
  uploadStatus.className = "upload-status";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/ingest`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    uploadStatus.textContent = `✓ ${data.filename} — ${data.chunks} chunks`;
    uploadStatus.className = "upload-status success";
  } catch (err) {
    uploadStatus.textContent = `✗ ${err.message}`;
    uploadStatus.className = "upload-status error";
  }

  // Reset file input
  fileInput.value = "";
}

// ── Chat submit ─────────────────────────────────────────────
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = userInput.value.trim();
  if (!question || isGenerating) return;

  // Hide welcome screen
  welcomeEl.style.display = "none";

  // Add user message
  appendMessage("user", question);

  // Clear input
  userInput.value = "";
  userInput.style.height = "auto";
  sendBtn.disabled = true;
  isGenerating = true;

  // Show typing indicator
  const typing = showTyping();

  try {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Query failed");

    removeTyping(typing);
    appendMessage("assistant", data.answer, data.sources);
  } catch (err) {
    removeTyping(typing);
    appendMessage("assistant", `⚠️ Error: ${err.message}`);
  }

  isGenerating = false;
});

// ── Helpers ─────────────────────────────────────────────────

function appendMessage(role, text, sources = []) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const label = document.createElement("span");
  label.className = "role-label";
  label.textContent = role === "user" ? "You" : "RAG Engine";
  div.appendChild(label);

  const body = document.createElement("span");
  body.textContent = text;
  div.appendChild(body);

  // Sources
  if (sources && sources.length) {
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "sources-toggle";
    toggleBtn.innerHTML = `📄 ${sources.length} source(s)`;
    div.appendChild(toggleBtn);

    const list = document.createElement("div");
    list.className = "sources-list";
    sources.forEach((s, i) => {
      const p = document.createElement("p");
      p.textContent = `[${i + 1}] ${s.source || "unknown"} (score: ${s.score ?? "n/a"})`;
      list.appendChild(p);

      const snippet = document.createElement("p");
      snippet.style.opacity = "0.7";
      snippet.style.marginBottom = "8px";
      snippet.textContent = s.content.slice(0, 200) + (s.content.length > 200 ? "…" : "");
      list.appendChild(snippet);
    });
    div.appendChild(list);

    toggleBtn.addEventListener("click", () => list.classList.toggle("open"));
  }

  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = "<span></span><span></span><span></span>";
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function removeTyping(el) {
  el?.remove();
}
