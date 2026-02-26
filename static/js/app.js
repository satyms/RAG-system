/* ═══════════════════════════════════════════════════════════
   RAG Engine — Frontend logic
   ═══════════════════════════════════════════════════════════ */

const API_BASE = "";  // same origin

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
