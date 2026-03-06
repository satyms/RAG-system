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
