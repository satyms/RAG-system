const { useEffect, useRef, useState } = React;

const API_BASE = "";
const STORAGE_KEY = "rag-engine-conversations";
const ACTIVE_STORAGE_KEY = "rag-engine-active-conversation";
const STUDIO_STORAGE_KEY = "rag-engine-studio-items";
const SUGGESTIONS = [
  "Summarize the uploaded document",
  "List the main concepts I should study",
  "Explain the topic in simple terms",
];

const STUDIO_ACTIONS = [
  {
    key: "flashcards",
    label: "Flashcards",
    description: "Generate question and answer cards for quick revision.",
    badge: "Practice",
  },
  {
    key: "quiz",
    label: "Quiz",
    description: "Build a multiple-choice quiz with hints and explanations.",
    badge: "Assess",
  },
  {
    key: "mind_map",
    label: "Mind Map",
    description: "Turn the indexed material into a structured concept map.",
    badge: "Visualize",
  },
];

marked.setOptions({
  gfm: true,
  breaks: true,
});

function generateId() {
  return `item-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
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
  return normalized.length > 36 ? `${normalized.slice(0, 36)}...` : normalized;
}

function renderMarkdown(content) {
  const html = marked.parse(content || "");
  return DOMPurify.sanitize(html);
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

function normalizeArtifact(rawArtifact) {
  if (!rawArtifact || typeof rawArtifact !== "object") {
    return null;
  }

  const sources = Array.isArray(rawArtifact.sources)
    ? rawArtifact.sources.filter((source) => source && typeof source.content === "string")
    : [];

  const artifactType = typeof rawArtifact.artifact_type === "string"
    ? rawArtifact.artifact_type
    : typeof rawArtifact.artifactType === "string"
      ? rawArtifact.artifactType
      : "flashcards";

  return {
    id: typeof rawArtifact.id === "string" ? rawArtifact.id : generateId(),
    artifactType,
    title: typeof rawArtifact.title === "string" && rawArtifact.title.trim()
      ? rawArtifact.title
      : "Untitled artifact",
    summary: typeof rawArtifact.summary === "string" ? rawArtifact.summary : "",
    content: rawArtifact.content && typeof rawArtifact.content === "object" ? rawArtifact.content : {},
    sources,
    createdAt: typeof rawArtifact.createdAt === "string" ? rawArtifact.createdAt : new Date().toISOString(),
  };
}

function loadStoredArtifacts() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STUDIO_STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map(normalizeArtifact).filter(Boolean);
  } catch {
    return [];
  }
}

function getSourceCount(sources) {
  const uniqueSources = new Set(
    (sources || []).map((source) => source.source).filter(Boolean),
  );
  return uniqueSources.size || (sources || []).length;
}

function formatRelativeTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "just now";
  }

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(1, Math.round(diffMs / 60000));
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
}

function artifactLabel(artifactType) {
  const action = STUDIO_ACTIONS.find((item) => item.key === artifactType);
  return action ? action.label : "Artifact";
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

  const uploadClassName = ["upload-area", isDragging ? "drag-active" : ""]
    .filter(Boolean)
    .join(" ");

  const statusClassName = ["upload-status", uploadStatus.type].filter(Boolean).join(" ");

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
        <div className="logo-mark">R</div>
        <div>
          <span className="logo-text">RAG Engine</span>
          <p className="logo-subtext">Chat, study, and review from one workspace.</p>
        </div>
      </div>

      <button type="button" className="new-chat-btn" onClick={onNewChat} disabled={isGenerating}>
        <span className="button-plus">+</span>
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
          <span className="upload-icon">+</span>
          <span>Drop file or click to upload</span>
          <span className="upload-hint">PDF, TXT, MD</span>
        </label>
        <div className={statusClassName}>{uploadStatus.message}</div>
      </div>

      <div className="sidebar-section sidebar-footer">
        <span className="version-tag">Indexed study workspace</span>
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
      <div className="message-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }} />

      {sources.length > 0 && (
        <>
          <button type="button" className="sources-toggle" onClick={() => setSourcesOpen((open) => !open)}>
            {sources.length} source(s)
          </button>
          <div className={`sources-list${sourcesOpen ? " open" : ""}`}>
            {sources.map((source, index) => (
              <div key={`${source.source || "source"}-${index}`} className="source-item">
                <p>[{index + 1}] {source.source || "unknown"} (score: {source.score ?? "n/a"})</p>
                <p className="source-snippet">
                  {typeof source.content === "string" && source.content.length > 200
                    ? `${source.content.slice(0, 200)}...`
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
        <div className="welcome-card">
          <div className="welcome-copy">
            <span className="eyebrow">Study-first RAG workspace</span>
            <h1>Upload a source, ask questions, and turn it into review material.</h1>
            <p>
              Use chat for explanation, then use the study tools above the conversation to generate flashcards, quizzes, and mind maps.
            </p>
          </div>
          <div className="suggestions">
            {SUGGESTIONS.map((suggestion) => (
              <button key={suggestion} type="button" className="suggestion" onClick={() => onSuggestionClick(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      ) : (
        messages.map((message, index) => <MessageBubble key={`${conversation.id}-${index}`} message={message} />)
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
          placeholder="Ask about your indexed document..."
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
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </form>
      <p className="disclaimer">Responses and study artifacts should be checked against the source material.</p>
    </div>
  );
}

function StudioActionCard({ action, onGenerate, isGenerating }) {
  return (
    <button
      type="button"
      className={`studio-action-card ${action.key}`}
      onClick={() => onGenerate(action.key)}
      disabled={isGenerating}
    >
      <div className="studio-action-topline">
        <span className="studio-action-badge">{action.badge}</span>
        <span className="studio-action-arrow">Open</span>
      </div>
      <h3>{action.label}</h3>
      <p>{action.description}</p>
    </button>
  );
}

function StudyToolsBar({ onGenerate, status, isGenerating }) {
  return (
    <section className="study-tools-bar">
      <div className="study-tools-header">
        <div>
          <span className="eyebrow">Study Tools</span>
          <h2>Generate from the indexed document</h2>
        </div>
        <div className={`studio-status ${status.type || "info"}`}>{status.message}</div>
      </div>

      <div className="study-tools-grid">
        {STUDIO_ACTIONS.map((action) => (
          <StudioActionCard key={action.key} action={action} onGenerate={onGenerate} isGenerating={isGenerating} />
        ))}
      </div>
    </section>
  );
}

function GeneratedArtifactItem({ item, onOpen, onDelete }) {
  return (
    <article className="artifact-feed-item">
      <button type="button" className="artifact-feed-main" onClick={() => onOpen(item)}>
        <div className="artifact-feed-icon">{artifactLabel(item.artifactType).slice(0, 1)}</div>
        <div className="artifact-feed-copy">
          <h3>{item.title}</h3>
          <p>{item.summary}</p>
          <span>
            {getSourceCount(item.sources)} source{getSourceCount(item.sources) === 1 ? "" : "s"} · {formatRelativeTime(item.createdAt)}
          </span>
        </div>
      </button>
      <button type="button" className="artifact-menu-btn" onClick={() => onDelete(item.id)} aria-label="Delete generated item">
        x
      </button>
    </article>
  );
}

function GeneratedContentFeed({ artifacts, onOpen, onDelete }) {
  return (
    <section className="generated-content-panel">
      <div className="generated-content-header">
        <div>
          <span className="eyebrow">Generated Content</span>
          <h2>Recent study items</h2>
        </div>
        <span className="generated-count">{artifacts.length}</span>
      </div>

      {artifacts.length ? (
        <div className="artifact-feed-list">
          {artifacts.map((item) => (
            <GeneratedArtifactItem key={item.id} item={item} onOpen={onOpen} onDelete={onDelete} />
          ))}
        </div>
      ) : (
        <div className="artifact-empty-state">
          Generate a flashcard set, a quiz, or a mind map. Each result is saved here for quick reopening.
        </div>
      )}
    </section>
  );
}

function RightDock({
  artifacts,
  onOpenArtifact,
  onDeleteArtifact,
  onGenerate,
  isGenerating,
  isOpen,
  onToggle,
}) {
  return (
    <aside className={`right-dock${isOpen ? " open" : ""}`}>
      <div className="right-dock-panel">
        <GeneratedContentFeed artifacts={artifacts} onOpen={onOpenArtifact} onDelete={onDeleteArtifact} />
      </div>

      <div className="right-dock-rail">
        <button
          type="button"
          className="right-dock-toggle"
          onClick={onToggle}
          aria-label={isOpen ? "Collapse generated content panel" : "Expand generated content panel"}
          title={isOpen ? "Collapse panel" : "Expand panel"}
        >
          <span>{isOpen ? ">" : "<"}</span>
        </button>

        {STUDIO_ACTIONS.map((action) => (
          <button
            key={action.key}
            type="button"
            className={`right-dock-action ${action.key}`}
            onClick={() => onGenerate(action.key)}
            disabled={isGenerating}
            title={action.label}
            aria-label={`Generate ${action.label}`}
          >
            <span>{action.label.slice(0, 2).toUpperCase()}</span>
          </button>
        ))}

        <button
          type="button"
          className="right-dock-count"
          onClick={onToggle}
          aria-label="Toggle generated content list"
          title="Generated content"
        >
          <span>{artifacts.length}</span>
        </button>
      </div>
    </aside>
  );
}

function FlashcardsViewer({ item }) {
  const cards = Array.isArray(item.content.cards) ? item.content.cards : [];
  const [activeIndex, setActiveIndex] = useState(0);
  const [isAnswerVisible, setIsAnswerVisible] = useState(false);
  const [knownIndices, setKnownIndices] = useState([]);
  const [reviewIndices, setReviewIndices] = useState([]);

  useEffect(() => {
    setActiveIndex(0);
    setIsAnswerVisible(false);
    setKnownIndices([]);
    setReviewIndices([]);
  }, [item.id]);

  if (!cards.length) {
    return <div className="modal-empty">No flashcards were returned.</div>;
  }

  const activeCard = cards[activeIndex];

  const markCard = (bucket, setter) => {
    setter((current) => (current.includes(activeIndex) ? current : [...current, activeIndex]));
    if (bucket === "known") {
      setReviewIndices((current) => current.filter((index) => index !== activeIndex));
    }
    if (bucket === "review") {
      setKnownIndices((current) => current.filter((index) => index !== activeIndex));
    }
    if (activeIndex < cards.length - 1) {
      setActiveIndex((index) => index + 1);
      setIsAnswerVisible(false);
    }
  };

  return (
    <div className="flashcards-viewer">
      <div className="viewer-metrics">
        <span>{activeIndex + 1} / {cards.length}</span>
        <span>{knownIndices.length} known</span>
        <span>{reviewIndices.length} review</span>
      </div>

      <button
        type="button"
        className={`flashcard-surface${isAnswerVisible ? " flipped" : ""}`}
        onClick={() => setIsAnswerVisible((visible) => !visible)}
      >
        <div className="flashcard-side flashcard-front">
          <span className="flashcard-label">Question</span>
          <p>{activeCard.question || "Question unavailable."}</p>
          <span className="flashcard-hint-text">Click card to reveal answer</span>
        </div>
        <div className="flashcard-side flashcard-back">
          <span className="flashcard-label">Answer</span>
          <p>{activeCard.answer || "Answer unavailable."}</p>
        </div>
      </button>

      <div className="viewer-actions">
        <button
          type="button"
          className="secondary-btn"
          onClick={() => {
            setActiveIndex((index) => Math.max(0, index - 1));
            setIsAnswerVisible(false);
          }}
          disabled={activeIndex === 0}
        >
          Previous
        </button>
        <button type="button" className="secondary-btn" onClick={() => markCard("review", setReviewIndices)}>
          Needs review
        </button>
        <button type="button" className="primary-btn" onClick={() => markCard("known", setKnownIndices)}>
          I know this
        </button>
      </div>
    </div>
  );
}

function QuizViewer({ item }) {
  const questions = Array.isArray(item.content.questions) ? item.content.questions : [];
  const [activeIndex, setActiveIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    setActiveIndex(0);
    setAnswers({});
    setShowHint(false);
  }, [item.id]);

  if (!questions.length) {
    return <div className="modal-empty">No quiz questions were returned.</div>;
  }

  const activeQuestion = questions[activeIndex];
  const answerIndex = answers[activeIndex];
  const isAnswered = typeof answerIndex === "number";
  const isLastQuestion = activeIndex === questions.length - 1;
  const correctAnswers = Object.entries(answers).reduce((count, [index, value]) => {
    const question = questions[Number(index)];
    return count + (question && value === question.answer_index ? 1 : 0);
  }, 0);

  return (
    <div className="quiz-viewer">
      <div className="viewer-metrics">
        <span>{activeIndex + 1} / {questions.length}</span>
        <span>{correctAnswers} correct</span>
      </div>

      <div className="quiz-question-block">
        <h3>{activeQuestion.question || "Question unavailable."}</h3>
        <div className="quiz-options">
          {(Array.isArray(activeQuestion.options) ? activeQuestion.options : []).map((option, optionIndex) => {
            const isSelected = answerIndex === optionIndex;
            const isCorrect = isAnswered && optionIndex === activeQuestion.answer_index;
            const isWrongSelection = isAnswered && isSelected && !isCorrect;
            const className = ["quiz-option", isSelected ? "selected" : "", isCorrect ? "correct" : "", isWrongSelection ? "wrong" : ""]
              .filter(Boolean)
              .join(" ");

            return (
              <button
                key={`${item.id}-${activeIndex}-${optionIndex}`}
                type="button"
                className={className}
                disabled={isAnswered}
                onClick={() => setAnswers((current) => ({ ...current, [activeIndex]: optionIndex }))}
              >
                <span className="quiz-option-letter">{String.fromCharCode(65 + optionIndex)}</span>
                <span>{option}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="quiz-footer">
        <button type="button" className="secondary-btn" onClick={() => setShowHint((value) => !value)}>
          {showHint ? "Hide hint" : "Hint"}
        </button>
        <button
          type="button"
          className="primary-btn"
          onClick={() => {
            setActiveIndex((index) => (isLastQuestion ? 0 : index + 1));
            setShowHint(false);
          }}
          disabled={!isAnswered}
        >
          {isLastQuestion ? "Restart" : "Next"}
        </button>
      </div>

      {showHint && activeQuestion.hint && <p className="quiz-hint">{activeQuestion.hint}</p>}
      {isAnswered && activeQuestion.explanation && <p className="quiz-explanation">{activeQuestion.explanation}</p>}
    </div>
  );
}

function MindMapBranch({ branch }) {
  const children = Array.isArray(branch.children) ? branch.children : [];

  return (
    <li>
      <div className="mind-map-node">{branch.label || "Untitled node"}</div>
      {children.length > 0 && (
        <ul>
          {children.map((child, index) => (
            <MindMapBranch key={`${branch.label || "node"}-${index}`} branch={child} />
          ))}
        </ul>
      )}
    </li>
  );
}

function MindMapViewer({ item }) {
  const centralTopic = item.content.central_topic || item.title;
  const branches = Array.isArray(item.content.branches) ? item.content.branches : [];

  if (!branches.length) {
    return <div className="modal-empty">No mind map branches were returned.</div>;
  }

  return (
    <div className="mind-map-viewer">
      <div className="mind-map-center">{centralTopic}</div>
      <div className="mind-map-tree">
        <ul>
          {branches.map((branch, index) => (
            <MindMapBranch key={`${item.id}-${index}`} branch={branch} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function ArtifactModal({ item, onClose }) {
  useEffect(() => {
    const handleKeydown = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [onClose]);

  let viewer = null;
  if (item.artifactType === "flashcards") {
    viewer = <FlashcardsViewer item={item} />;
  } else if (item.artifactType === "quiz") {
    viewer = <QuizViewer item={item} />;
  } else {
    viewer = <MindMapViewer item={item} />;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="artifact-modal" onClick={(event) => event.stopPropagation()}>
        <div className="artifact-modal-header">
          <div>
            <span className="eyebrow">{artifactLabel(item.artifactType)}</span>
            <h2>{item.title}</h2>
            <p>{item.summary}</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close artifact viewer">
            x
          </button>
        </div>
        <div className="artifact-modal-meta">
          <span>Based on {getSourceCount(item.sources)} source{getSourceCount(item.sources) === 1 ? "" : "s"}</span>
          <span>{formatRelativeTime(item.createdAt)}</span>
        </div>
        <div className="artifact-modal-body">{viewer}</div>
      </div>
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
      studioArtifacts: loadStoredArtifacts(),
    };
  }

  const [conversations, setConversations] = useState(initialStateRef.current.conversations);
  const [activeConversationId, setActiveConversationId] = useState(initialStateRef.current.activeConversationId);
  const [inputValue, setInputValue] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState(null);
  const [uploadStatus, setUploadStatus] = useState({ message: "", type: "" });
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [artifacts, setArtifacts] = useState(initialStateRef.current.studioArtifacts);
  const [activeArtifact, setActiveArtifact] = useState(null);
  const [isStudioGenerating, setIsStudioGenerating] = useState(false);
  const [isRightDockOpen, setIsRightDockOpen] = useState(() => window.innerWidth > 1180);
  const [studioStatus, setStudioStatus] = useState({
    message: "Upload a document, then generate flashcards, a quiz, or a mind map.",
    type: "info",
  });

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) || conversations[0];

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    localStorage.setItem(STUDIO_STORAGE_KEY, JSON.stringify(artifacts));
  }, [artifacts]);

  useEffect(() => {
    if (!conversations.some((conversation) => conversation.id === activeConversationId)) {
      setActiveConversationId(conversations[0]?.id || null);
      return;
    }

    if (activeConversationId) {
      localStorage.setItem(ACTIVE_STORAGE_KEY, activeConversationId);
    }
  }, [activeConversationId, conversations]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 900) {
        setIsRightDockOpen(false);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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
        message: `${data.filename} indexed · ${data.chunks} chunks`,
        type: "success",
      });
      setStudioStatus({
        message: "Document indexed. Studio generation is ready.",
        type: "success",
      });
    } catch (error) {
      setUploadStatus({ message: error.message, type: "error" });
      setStudioStatus({ message: error.message, type: "error" });
    }
  };

  const handleGenerateArtifact = async (artifactType) => {
    if (isStudioGenerating) {
      return;
    }

    setIsStudioGenerating(true);
    setStudioStatus({
      message: `Generating ${artifactLabel(artifactType).toLowerCase()}...`,
      type: "info",
    });

    try {
      const response = await fetch(`${API_BASE}/api/studio/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ artifact_type: artifactType }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Artifact generation failed");
      }

      const artifact = normalizeArtifact({
        ...data,
        id: generateId(),
        createdAt: new Date().toISOString(),
      });

      setArtifacts((currentArtifacts) => [artifact, ...currentArtifacts]);
      setActiveArtifact(artifact);
      setStudioStatus({
        message: `${artifact.title} generated and saved below chat.`,
        type: "success",
      });
    } catch (error) {
      setStudioStatus({
        message: error.message,
        type: "error",
      });
    } finally {
      setIsStudioGenerating(false);
    }
  };

  const handleDeleteArtifact = (artifactId) => {
    setArtifacts((currentArtifacts) => currentArtifacts.filter((artifact) => artifact.id !== artifactId));
    setActiveArtifact((currentArtifact) => (currentArtifact && currentArtifact.id === artifactId ? null : currentArtifact));
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
        isGenerating={isGenerating || isStudioGenerating}
      />

      <button type="button" className="sidebar-toggle" onClick={() => setIsSidebarOpen((open) => !open)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <main className="workspace-shell">
        <section className="chat-panel">
          <div className="chat-surface">
            <StudyToolsBar onGenerate={handleGenerateArtifact} status={studioStatus} isGenerating={isStudioGenerating} />
            <ChatWindow conversation={activeConversation} isLoading={loadingConversationId === activeConversationId} onSuggestionClick={sendMessage} />
            <ChatInput value={inputValue} onChange={setInputValue} onSubmit={() => sendMessage()} disabled={isGenerating} />
          </div>
        </section>

        <RightDock
          artifacts={artifacts}
          onOpenArtifact={setActiveArtifact}
          onDeleteArtifact={handleDeleteArtifact}
          onGenerate={handleGenerateArtifact}
          isGenerating={isStudioGenerating}
          isOpen={isRightDockOpen}
          onToggle={() => setIsRightDockOpen((open) => !open)}
        />
      </main>

      {activeArtifact && <ArtifactModal item={activeArtifact} onClose={() => setActiveArtifact(null)} />}
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);