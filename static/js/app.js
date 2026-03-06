const { useEffect, useRef, useState } = React;

const API_BASE = "";
const STORAGE_KEY = "rag-engine-conversations";
const ACTIVE_STORAGE_KEY = "rag-engine-active-conversation";
const SUGGESTIONS = [
  "Summarize the uploaded document",
  "What are the key points?",
  "Explain in simple terms",
];

marked.setOptions({
  gfm: true,
  breaks: true,
});

function generateId() {
  return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function createConversation() {
  return {
    id: generateId(),
    title: "New Chat",
    messages: [],
  };
}

function deriveTitle(content) {
  const normalized = content.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "New Chat";
﻿/* ================================================================
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
  return normalized.length > 36 ? `${normalized.slice(0, 36)}…` : normalized;
}

function loadStoredConversations() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed) || !parsed.length) {
      return [createConversation()];
    }

    const sanitized = parsed
      .filter((conversation) => conversation && typeof conversation.id === "string")
      .map((conversation) => ({
        id: conversation.id,
        title: typeof conversation.title === "string" && conversation.title.trim()
          ? conversation.title
          : "New Chat",
        messages: Array.isArray(conversation.messages)
          ? conversation.messages.filter((message) => message && typeof message.content === "string")
          : [],
      }));

    return sanitized.length ? sanitized : [createConversation()];
  } catch {
    return [createConversation()];
  }
}

function loadStoredActiveConversationId(conversations) {
  const storedId = localStorage.getItem(ACTIVE_STORAGE_KEY);
  if (storedId && conversations.some((conversation) => conversation.id === storedId)) {
    return storedId;
  }
  return conversations[0].id;
}

function renderMarkdown(content) {
  const html = marked.parse(content || "");
  return DOMPurify.sanitize(html);
}

function updateConversationMessages(conversations, conversationId, updater) {
  const index = conversations.findIndex((conversation) => conversation.id === conversationId);
  if (index === -1) {
    return conversations;
  }

  const conversation = conversations[index];
  const updatedConversation = updater(conversation);
  const nextConversations = conversations.slice();
  nextConversations.splice(index, 1);
  nextConversations.unshift(updatedConversation);
  return nextConversations;
}

function ChatHistoryItem({ conversation, isActive, onSelect, disabled }) {
  return (
    <button
      type="button"
      className={`chat-history-item${isActive ? " active" : ""}`}
      onClick={() => onSelect(conversation.id)}
      disabled={disabled}
      title={conversation.title}
    >
      <span className="chat-history-title">{conversation.title}</span>
    </button>
  );
}

function Sidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  uploadStatus,
  onFileUpload,
  isSidebarOpen,
  onCloseSidebar,
  isGenerating,
}) {
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const uploadClassName = [
    "upload-area",
    isDragging ? "drag-active" : "",
  ].filter(Boolean).join(" ");

  const statusClassName = [
    "upload-status",
    uploadStatus.type,
  ].filter(Boolean).join(" ");

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const [file] = event.dataTransfer.files || [];
    if (file) {
      onFileUpload(file);
    }
  };

  return (
    <aside className={`sidebar${isSidebarOpen ? " open" : ""}`}>
      <div className="sidebar-header">
        <svg className="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span className="logo-text">RAG Engine</span>
      </div>

      <button type="button" className="new-chat-btn" onClick={onNewChat} disabled={isGenerating}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        New Chat
      </button>

      <div className="sidebar-section sidebar-history-section">
        <h3>Chats</h3>
        <div className="chat-history-list">
          {conversations.length ? (
            conversations.map((conversation) => (
              <ChatHistoryItem
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === activeConversationId}
                onSelect={(conversationId) => {
                  onSelectConversation(conversationId);
                  onCloseSidebar();
                }}
                disabled={false}
              />
            ))
          ) : (
            <div className="chat-history-empty">No conversations yet.</div>
          )}
        </div>
      </div>

      <div className="sidebar-section">
        <h3>Upload Documents</h3>
        <label
          className={uploadClassName}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md"
            hidden
            onChange={(event) => {
              const [file] = event.target.files || [];
              if (file) {
                onFileUpload(file);
              }
              event.target.value = "";
            }}
          />
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="28" height="28">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <span>Drop file or click to upload</span>
          <span className="upload-hint">PDF, TXT, MD</span>
        </label>
        <div className={statusClassName}>{uploadStatus.message}</div>
      </div>

      <div className="sidebar-section sidebar-footer">
        <span className="version-tag">v1.0.0</span>
      </div>
    </aside>
  );
}

function MessageBubble({ message }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sources = Array.isArray(message.sources) ? message.sources : [];

  return (
    <div className={`message ${message.role}`}>
      <span className="role-label">{message.role === "user" ? "You" : "RAG Engine"}</span>
      <div
        className="message-content"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
      />

      {sources.length > 0 && (
        <>
          <button
            type="button"
            className="sources-toggle"
            onClick={() => setSourcesOpen((open) => !open)}
          >
            {sources.length} source(s)
          </button>
          <div className={`sources-list${sourcesOpen ? " open" : ""}`}>
            {sources.map((source, index) => (
              <div key={`${source.source || "source"}-${index}`} className="source-item">
                <p>[{index + 1}] {source.source || "unknown"} (score: {source.score ?? "n/a"})</p>
                <p className="source-snippet">
                  {typeof source.content === "string" && source.content.length > 200
                    ? `${source.content.slice(0, 200)}…`
                    : source.content || ""}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ChatWindow({ conversation, isLoading, onSuggestionClick }) {
  const messagesRef = useRef(null);
  const messages = conversation?.messages || [];

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages, isLoading, conversation?.id]);

  return (
    <div className="messages" ref={messagesRef}>
      {!messages.length ? (
        <div className="welcome">
          <div className="welcome-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <h1>How can I help you today?</h1>
          <p>Upload a document and ask questions about it, or just start chatting.</p>
          <div className="suggestions">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="suggestion"
                onClick={() => onSuggestionClick(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      ) : (
        messages.map((message, index) => (
          <MessageBubble key={`${conversation.id}-${index}`} message={message} />
        ))
      )}

      {isLoading && (
        <div className="typing-indicator" aria-live="polite" aria-label="Assistant is typing">
          <span></span>
          <span></span>
          <span></span>
        </div>
      )}
    </div>
  );
}

function ChatInput({ value, onChange, onSubmit, disabled }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!textareaRef.current) {
      return;
    }

    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
  }, [value]);

  return (
    <div className="input-wrapper">
      <form
        className="input-area"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          placeholder="Message RAG Engine…"
          rows="1"
          autoComplete="off"
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
        />
        <button type="submit" className="send-btn" disabled={disabled || !value.trim()}>
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </form>
      <p className="disclaimer">RAG Engine may produce inaccurate information. Verify important facts.</p>
    </div>
  );
}

function App() {
  const initialStateRef = useRef(null);

  if (!initialStateRef.current) {
    const initialConversations = loadStoredConversations();
    initialStateRef.current = {
      conversations: initialConversations,
      activeConversationId: loadStoredActiveConversationId(initialConversations),
    };
  }

  const [conversations, setConversations] = useState(initialStateRef.current.conversations);
  const [activeConversationId, setActiveConversationId] = useState(initialStateRef.current.activeConversationId);
  const [inputValue, setInputValue] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState(null);
  const [uploadStatus, setUploadStatus] = useState({ message: "", type: "" });
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) || conversations[0];

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    if (!conversations.some((conversation) => conversation.id === activeConversationId)) {
      setActiveConversationId(conversations[0]?.id || null);
      return;
    }

    if (activeConversationId) {
      localStorage.setItem(ACTIVE_STORAGE_KEY, activeConversationId);
    }
  }, [activeConversationId, conversations]);

  const createNewChat = () => {
    const conversation = createConversation();
    setConversations((currentConversations) => [conversation, ...currentConversations]);
    setActiveConversationId(conversation.id);
    setInputValue("");
    setIsSidebarOpen(false);
  };

  const appendAssistantMessage = (conversationId, content, sources = []) => {
    setConversations((currentConversations) => updateConversationMessages(
      currentConversations,
      conversationId,
      (conversation) => ({
        ...conversation,
        messages: [...conversation.messages, { role: "assistant", content, sources }],
      }),
    ));
  };

  const sendMessage = async (presetValue) => {
    const question = (typeof presetValue === "string" ? presetValue : inputValue).trim();
    if (!question || isGenerating || !activeConversation) {
      return;
    }

    const targetConversationId = activeConversation.id;
    setConversations((currentConversations) => updateConversationMessages(
      currentConversations,
      targetConversationId,
      (conversation) => ({
        ...conversation,
        title: conversation.messages.length ? conversation.title : deriveTitle(question),
        messages: [...conversation.messages, { role: "user", content: question }],
      }),
    ));
    setActiveConversationId(targetConversationId);
    setInputValue("");
    setIsGenerating(true);
    setLoadingConversationId(targetConversationId);

    try {
      const response = await fetch(`${API_BASE}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Query failed");
      }

      appendAssistantMessage(targetConversationId, data.answer || "", data.sources || []);
    } catch (error) {
      appendAssistantMessage(targetConversationId, `Error: ${error.message}`);
    } finally {
      setIsGenerating(false);
      setLoadingConversationId(null);
    }
  };

  const handleFileUpload = async (file) => {
    setUploadStatus({ message: `Uploading ${file.name}...`, type: "" });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      setUploadStatus({
        message: `${data.filename} - ${data.chunks} chunks`,
        type: "success",
      });
    } catch (error) {
      setUploadStatus({ message: error.message, type: "error" });
    }
  };

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversationId}
        onNewChat={createNewChat}
        uploadStatus={uploadStatus}
        onFileUpload={handleFileUpload}
        isSidebarOpen={isSidebarOpen}
        onCloseSidebar={() => setIsSidebarOpen(false)}
        isGenerating={isGenerating}
      />

      <button type="button" className="sidebar-toggle" onClick={() => setIsSidebarOpen((open) => !open)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="22" height="22">
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <main className="chat-main">
        <ChatWindow
          conversation={activeConversation}
          isLoading={loadingConversationId === activeConversationId}
          onSuggestionClick={sendMessage}
        />
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSubmit={() => sendMessage()}
          disabled={isGenerating}
        />
      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
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

