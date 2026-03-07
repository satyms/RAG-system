const API_BASE = "";
const APP_STORAGE_KEY = "rag-workspace-state";
const APP_STORAGE_VERSION = 3;
const QUICK_PROMPTS = [
  "Summarize the selected sources",
  "Compare the research findings",
  "Turn this into a study guide",
];

const STUDIO_TOOLS = [
  { id: "audio", label: "Audio Overview", icon: "🎧", comingSoon: true },
  { id: "video", label: "Video Overview", icon: "🎬", comingSoon: true },
  { id: "mind-map", label: "Mind Map", icon: "🧠" },
  { id: "reports", label: "Reports", icon: "📊" },
  { id: "flashcards", label: "Flashcards", icon: "🗂" },
  { id: "quiz", label: "Quiz", icon: "❓" },
  { id: "infographic", label: "Infographic", icon: "🧾" },
  { id: "slides", label: "Slide Deck", icon: "🖥" },
  { id: "table", label: "Data Table", icon: "🧮" },
];

const defaultSources = [
  { id: 1, title: "Research Paper.pdf", type: "documents", selected: true, icon: "📄" },
  { id: 2, title: "LLM Systems Review", type: "research", selected: true, icon: "🧪" },
  { id: 3, title: "documentation.com/rag", type: "web", selected: false, icon: "🌐" },
  { id: 4, title: "Vector Database Notes.md", type: "documents", selected: false, icon: "📝" },
  { id: 5, title: "Arxiv RAG Benchmark", type: "research", selected: false, icon: "📚" },
  { id: 6, title: "Engineering Blog Article", type: "web", selected: false, icon: "🔗" },
];

const defaultMessages = [];

const defaultGeneratedNotes = [];

marked.setOptions({
  gfm: true,
  breaks: true,
});

const state = loadState();

const elements = {
  sourceSearch: document.getElementById("source-search"),
  sourceFilter: document.getElementById("source-filter"),
  sourcesList: document.getElementById("sources-list"),
  selectedSourceCount: document.getElementById("selected-source-count"),
  selectedSourcesBar: document.getElementById("selected-sources-bar"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  sendButton: document.getElementById("send-button"),
  messagesContainer: document.getElementById("messages-container"),
  studioToolsGrid: document.getElementById("studio-tools-grid"),
  generatedNotesList: document.getElementById("generated-notes-list"),
  addSourcesButton: document.getElementById("add-sources-button"),
  sourceFileInput: document.getElementById("source-file-input"),
  addNoteButton: document.getElementById("add-note-button"),
  clearHistoryButton: document.getElementById("clear-history-button"),
  artifactViewer: document.getElementById("artifact-viewer"),
  viewerTitle: document.getElementById("viewer-title"),
  viewerMeta: document.getElementById("viewer-meta"),
  viewerBody: document.getElementById("viewer-body"),
  viewerCloseButton: document.getElementById("viewer-close-button"),
};

const viewerRuntime = {
  chart: null,
  reveal: null,
};

initialize();

function initialize() {
  bindEvents();
  renderStudioTools();
  renderApp();
}

function loadState() {
  try {
    const stored = JSON.parse(localStorage.getItem(APP_STORAGE_KEY) || "{}");
    const sameVersion = stored.storageVersion === APP_STORAGE_VERSION;
    const sources = Array.isArray(stored.sources) && stored.sources.length ? stored.sources : defaultSources;
    const messages = sameVersion && Array.isArray(stored.messages) ? stored.messages : defaultMessages;
    const generatedNotes = sameVersion && Array.isArray(stored.generatedNotes)
      ? stored.generatedNotes.map(normalizeGeneratedNote)
      : defaultGeneratedNotes;

    return {
      sources: sources.map(normalizeSourceRecord),
      selectedSources: deriveSelectedSources(sources),
      messages,
      generatedNotes,
      activeOutputId: generatedNotes[0]?.id || null,
      sourceSearch: typeof stored.sourceSearch === "string" ? stored.sourceSearch : "",
      sourceFilter: typeof stored.sourceFilter === "string" ? stored.sourceFilter : "all",
      isLoading: false,
    };
  } catch {
    return {
      sources: defaultSources,
      selectedSources: deriveSelectedSources(defaultSources),
      messages: defaultMessages,
      generatedNotes: defaultGeneratedNotes,
      activeOutputId: null,
      sourceSearch: "",
      sourceFilter: "all",
      isLoading: false,
    };
  }
}

function saveState() {
  const persisted = {
    storageVersion: APP_STORAGE_VERSION,
    sources: state.sources,
    messages: state.messages,
    generatedNotes: state.generatedNotes,
    sourceSearch: state.sourceSearch,
    sourceFilter: state.sourceFilter,
  };
  localStorage.setItem(APP_STORAGE_KEY, JSON.stringify(persisted));
}

function deriveSelectedSources(sources) {
  return sources.filter((source) => source.selected).map((source) => source.title);
}

function bindEvents() {
  elements.sourceSearch.value = state.sourceSearch;
  elements.sourceFilter.value = state.sourceFilter;

  elements.sourceSearch.addEventListener("input", (event) => {
    state.sourceSearch = event.target.value;
    renderSources();
    saveState();
  });

  elements.sourceFilter.addEventListener("change", (event) => {
    state.sourceFilter = event.target.value;
    renderSources();
    saveState();
  });

  elements.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await handleSendMessage();
  });

  elements.chatInput.addEventListener("keydown", async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await handleSendMessage();
    }
  });

  elements.chatInput.addEventListener("input", autoResizeTextarea);

  elements.addSourcesButton.addEventListener("click", () => {
    elements.sourceFileInput.click();
  });

  elements.sourceFileInput.addEventListener("change", async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) {
      return;
    }

    await handleSourceUpload(files);
    event.target.value = "";
  });

  elements.addNoteButton.addEventListener("click", () => {
    const noteNumber = state.generatedNotes.length + 1;
    const note = {
      id: Date.now(),
      title: `New Workspace Note ${noteNumber}`,
      meta: `${Math.max(state.selectedSources.length, 1)} source${state.selectedSources.length === 1 ? "" : "s"} • just now`,
      preview: "Add a generated artifact from the Studio tools to populate this note.",
      toolId: "reports",
      artifactData: createReportArtifactData(getToolContextSources()),
    };
    state.generatedNotes.unshift(note);
    state.activeOutputId = note.id;
    renderGeneratedNotes();
    openArtifactViewer(note.id);
    saveState();
  });

  elements.clearHistoryButton.addEventListener("click", clearHistory);
  elements.viewerCloseButton.addEventListener("click", closeArtifactViewer);
  elements.artifactViewer.addEventListener("click", (event) => {
    if (event.target === elements.artifactViewer) {
      closeArtifactViewer();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.artifactViewer.classList.contains("is-hidden")) {
      closeArtifactViewer();
    }
  });
}

function renderApp() {
  renderSources();
  renderSelectedSourcesBar();
  renderMessages();
  renderGeneratedNotes();
  updateSendButtonState();
  autoResizeTextarea();
}

function renderSources() {
  const filteredSources = getFilteredSources();

  elements.sourcesList.innerHTML = "";
  elements.selectedSourceCount.textContent = `${state.selectedSources.length} selected`;

  if (!filteredSources.length) {
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "No sources match the current search.";
    elements.sourcesList.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();

  filteredSources.forEach((source) => {
    const label = document.createElement("label");
    label.className = `source-item${source.selected ? " is-selected" : ""}`;
    label.setAttribute("role", "listitem");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = source.selected;
    checkbox.setAttribute("aria-label", `Select ${source.title}`);
    checkbox.addEventListener("change", () => toggleSourceSelection(source.id));

    const icon = document.createElement("span");
    icon.className = "source-icon";
    icon.textContent = source.icon;

    const copy = document.createElement("div");
    copy.className = "source-copy";
    copy.innerHTML = `
      <div class="source-title-row">
        <span class="source-title"></span>
      </div>
      <span class="source-type"></span>
    `;
    copy.querySelector(".source-title").textContent = source.title;
    copy.querySelector(".source-type").textContent = source.type;
    if (source.uploaded) {
      const badge = document.createElement("span");
      badge.className = "source-badge";
      badge.textContent = "Uploaded";
      copy.querySelector(".source-title-row").appendChild(badge);
    }

    label.appendChild(checkbox);
    label.appendChild(icon);
    label.appendChild(copy);
    fragment.appendChild(label);
  });

  elements.sourcesList.appendChild(fragment);
}

function renderSelectedSourcesBar() {
  elements.selectedSourcesBar.innerHTML = "";

  if (!state.selectedSources.length) {
    const placeholder = document.createElement("span");
    placeholder.className = "section-meta";
    placeholder.textContent = "No sources selected. Responses will rely on general context.";
    elements.selectedSourcesBar.appendChild(placeholder);
    return;
  }

  state.selectedSources.forEach((title) => {
    const chip = document.createElement("span");
    chip.className = "selection-chip";
    chip.textContent = title;
    elements.selectedSourcesBar.appendChild(chip);
  });
}

function renderMessages() {
  elements.messagesContainer.innerHTML = "";

  if (!state.messages.length) {
    elements.messagesContainer.appendChild(createEmptyState());
  } else {
    const fragment = document.createDocumentFragment();
    state.messages.forEach((message) => {
      fragment.appendChild(createMessageRow(message));
    });
    elements.messagesContainer.appendChild(fragment);
  }

  if (state.isLoading) {
    elements.messagesContainer.appendChild(createLoadingIndicator());
  }

  scrollMessagesToBottom();
}

function renderStudioTools() {
  elements.studioToolsGrid.innerHTML = "";

  STUDIO_TOOLS.forEach((tool) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tool-card${tool.comingSoon ? " is-coming-soon" : ""}`;
    button.disabled = Boolean(tool.comingSoon);
    button.innerHTML = `
      <span class="tool-card-head">
        <span class="tool-icon" aria-hidden="true">${tool.icon}</span>
        ${tool.comingSoon ? '<span class="tool-badge">Coming Soon</span>' : ""}
      </span>
      <span class="tool-label">${tool.label}</span>
      <span class="tool-helper">${tool.comingSoon ? "Unavailable for now" : "Generate from uploaded documents"}</span>
    `;
    button.addEventListener("click", () => {
      handleStudioTool(tool);
    });
    elements.studioToolsGrid.appendChild(button);
  });
}

function renderGeneratedNotes() {
  elements.generatedNotesList.innerHTML = "";

  if (!state.generatedNotes.length) {
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "No outputs yet.";
    elements.generatedNotesList.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();

  state.generatedNotes.forEach((note) => {
    const article = document.createElement("article");
    article.className = `note-card${note.id === state.activeOutputId ? " is-active" : ""}`;
    article.innerHTML = `
      <h3 class="note-title"></h3>
      <p class="note-meta"></p>
      <div class="note-preview"></div>
    `;
    article.querySelector(".note-title").textContent = note.title;
    article.querySelector(".note-meta").textContent = note.meta;
    article.querySelector(".note-preview").textContent = note.preview || "";
    article.addEventListener("click", () => openArtifactViewer(note.id));
    fragment.appendChild(article);
  });

  elements.generatedNotesList.appendChild(fragment);
}

function getFilteredSources() {
  const search = state.sourceSearch.trim().toLowerCase();
  return state.sources.filter((source) => {
    const matchesFilter = state.sourceFilter === "all" || source.type === state.sourceFilter;
    const matchesSearch = !search || source.title.toLowerCase().includes(search);
    return matchesFilter && matchesSearch;
  });
}

function toggleSourceSelection(sourceId) {
  state.sources = state.sources.map((source) => (
    source.id === sourceId ? { ...source, selected: !source.selected } : source
  ));
  state.selectedSources = deriveSelectedSources(state.sources);
  renderSources();
  renderSelectedSourcesBar();
  saveState();
}

function createEmptyState() {
  const wrapper = document.createElement("section");
  wrapper.className = "empty-state";

  const title = document.createElement("h3");
  title.textContent = "Ask across your sources";

  const copy = document.createElement("p");
  copy.textContent = "Use the left panel to select documents, research, or web sources. The assistant will combine that context with your prompt and cite what it used in every response.";

  const prompts = document.createElement("div");
  prompts.className = "quick-prompts";

  QUICK_PROMPTS.forEach((promptText) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "prompt-chip";
    button.textContent = promptText;
    button.addEventListener("click", () => {
      elements.chatInput.value = promptText;
      autoResizeTextarea();
      updateSendButtonState();
      elements.chatInput.focus();
    });
    prompts.appendChild(button);
  });

  wrapper.appendChild(title);
  wrapper.appendChild(copy);
  wrapper.appendChild(prompts);
  return wrapper;
}

function createMessageRow(message) {
  const row = document.createElement("div");
  row.className = `message-row ${message.role}`;

  const bubble = document.createElement("article");
  bubble.className = "message-bubble";

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = message.role === "user" ? "You" : "Assistant";

  const body = document.createElement("div");
  body.className = "message-body";
  body.innerHTML = DOMPurify.sanitize(marked.parse(message.content || ""));

  bubble.appendChild(label);
  bubble.appendChild(body);

  if (message.role === "assistant" && Array.isArray(message.sources) && message.sources.length) {
    bubble.appendChild(createSourcesUsedSection(message.sources));
  }

  row.appendChild(bubble);
  return row;
}

function createSourcesUsedSection(sources) {
  const section = document.createElement("section");
  section.className = "sources-used";

  const heading = document.createElement("h4");
  heading.textContent = "Sources Used";
  section.appendChild(heading);

  sources.forEach((source, index) => {
    const item = document.createElement("div");
    item.className = "source-reference";

    const marker = document.createElement("span");
    marker.className = "source-reference-index";
    marker.textContent = `[${index + 1}]`;

    const copy = document.createElement("span");
    copy.textContent = source.label || source.source || "Unknown source";

    item.appendChild(marker);
    item.appendChild(copy);
    section.appendChild(item);
  });

  return section;
}

function createLoadingIndicator() {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const indicator = document.createElement("div");
  indicator.className = "loading-indicator";
  indicator.innerHTML = `
    <span>Thinking</span>
    <span class="loading-dots" aria-hidden="true"><span></span><span></span><span></span></span>
  `;

  row.appendChild(indicator);
  return row;
}

function autoResizeTextarea() {
  elements.chatInput.style.height = "auto";
  elements.chatInput.style.height = `${Math.min(elements.chatInput.scrollHeight, 180)}px`;
  updateSendButtonState();
}

function updateSendButtonState() {
  elements.sendButton.disabled = state.isLoading || !elements.chatInput.value.trim();
}

function scrollMessagesToBottom() {
  requestAnimationFrame(() => {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
  });
}

async function handleSendMessage() {
  const content = elements.chatInput.value.trim();
  if (!content || state.isLoading) {
    return;
  }

  state.messages.push({ role: "user", content });
  elements.chatInput.value = "";
  autoResizeTextarea();

  state.isLoading = true;
  renderMessages();
  saveState();

  try {
    const response = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: content }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Query failed");
    }

    state.messages.push({
      role: "assistant",
      content: data.answer || "No answer returned.",
      sources: normalizeSources(data.sources),
    });
  } catch (error) {
    state.messages.push({
      role: "assistant",
      content: [
        "The workspace used a fallback response because the query service was unavailable.",
        "",
        `Error: ${error.message}`,
      ].join("\n"),
      sources: state.selectedSources.map((title) => ({ label: title })),
    });
  } finally {
    state.isLoading = false;
    renderMessages();
    saveState();
  }
}

async function handleSourceUpload(files) {
  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      state.sources.unshift({
        id: Date.now() + Math.random(),
        title: data.filename || file.name,
        type: "documents",
        selected: true,
        icon: "📄",
        uploaded: true,
      });
      pushStatusMessage(`Indexed **${data.filename || file.name}** with ${data.chunks || 0} chunk${data.chunks === 1 ? "" : "s"}.`, [data.filename || file.name]);
    } catch {
      state.sources.unshift({
        id: Date.now() + Math.random(),
        title: file.name,
        type: "documents",
        selected: true,
        icon: "📄",
        uploaded: true,
      });
      pushStatusMessage(`Added **${file.name}** to the workspace source list.`, [file.name]);
    }
  }

  state.selectedSources = deriveSelectedSources(state.sources);
  renderSources();
  renderSelectedSourcesBar();
  renderMessages();
  saveState();
}

function normalizeSources(sources) {
  if (!Array.isArray(sources) || !sources.length) {
    return state.selectedSources.map((title) => ({ label: title }));
  }

  return sources.map((source) => ({
    label: source.source || source.label || source.title || "Unknown source",
  }));
}

function normalizeSourceRecord(source) {
  return {
    uploaded: false,
    ...source,
  };
}

function clearHistory() {
  state.messages = [];
  state.generatedNotes = [];
  state.activeOutputId = null;
  state.isLoading = false;
  renderMessages();
  renderGeneratedNotes();
  closeArtifactViewer();
  saveState();
}

function pushStatusMessage(content, sourceLabels = []) {
  state.messages.push({
    role: "assistant",
    content,
    sources: sourceLabels.map((label) => ({ label })),
  });
}

function handleStudioTool(tool) {
  const contextSources = getToolContextSources();

  if (!contextSources.length) {
    pushStatusMessage(
      `Upload and select at least one document before generating a ${tool.label.toLowerCase()}.`,
      [],
    );
    renderMessages();
    saveState();
    return;
  }

  const artifact = buildArtifact(tool, contextSources);
  const note = {
    id: Date.now(),
    title: artifact.noteTitle,
    meta: `${contextSources.length} source${contextSources.length === 1 ? "" : "s"} • just now`,
    preview: artifact.preview,
    toolId: tool.id,
    artifactData: artifact.data,
  };
  state.generatedNotes.unshift(note);
  state.activeOutputId = note.id;
  state.messages.push({
    role: "assistant",
    content: `${artifact.message}\n\nOpen **${artifact.noteTitle}** from Recent Outputs to interact with it.`,
    sources: contextSources.map((source) => ({ label: source.title })),
  });
  renderGeneratedNotes();
  renderMessages();
  openArtifactViewer(note.id);
  saveState();
}

function getToolContextSources() {
  const selectedUploaded = state.sources.filter((source) => source.selected && source.uploaded);
  if (selectedUploaded.length) {
    return selectedUploaded;
  }

  return state.sources.filter((source) => source.selected);
}

function buildArtifact(tool, sources) {
  const sourceTitles = sources.map((source) => source.title);
  const shortList = sourceTitles.slice(0, 3).join(", ");
  const primaryTitle = sourceTitles[0] || "Selected Sources";

  const byTool = {
    "mind-map": {
      noteTitle: `Mind Map for ${primaryTitle}`,
      preview: `Clustered key ideas from ${shortList}.`,
      message: [
        `# Mind Map Draft`,
        `Built a concept map from **${shortList}**.`,
        ``,
        `- Core concept: problem framing`,
        `- Branches: definitions, workflow, tradeoffs, evaluation`,
        `- Follow-up: expand each branch into deeper notes`,
      ].join("\n"),
      data: createMindMapArtifactData(sources),
    },
    reports: {
      noteTitle: `Report Summary for ${primaryTitle}`,
      preview: `Executive summary and section outline generated from ${shortList}.`,
      message: [
        `# Report Draft`,
        `Prepared a concise report structure using **${shortList}**.`,
        ``,
        `## Sections`,
        `1. Scope and background`,
        `2. Key findings`,
        `3. Risks and constraints`,
        `4. Recommended next steps`,
      ].join("\n"),
      data: createReportArtifactData(sources),
    },
    flashcards: {
      noteTitle: `Flashcards from ${primaryTitle}`,
      preview: `Question and answer prompts extracted from uploaded material.`,
      message: [
        `# Flashcard Set`,
        `Generated revision prompts from **${shortList}**.`,
        ``,
        `- Q: What is the main concept introduced?`,
        `- A: Summarize the central definition and its role in the workflow.`,
        `- Q: Which tradeoff matters most?`,
        `- A: Compare precision, speed, and reliability.`,
      ].join("\n"),
      data: createFlashcardsArtifactData(sources),
    },
    quiz: {
      noteTitle: `Quiz for ${primaryTitle}`,
      preview: `Short comprehension quiz built from selected documents.`,
      message: [
        `# Quiz Draft`,
        `Created a short quiz from **${shortList}**.`,
        ``,
        `1. Which section explains the main workflow?`,
        `2. What evidence supports the final recommendation?`,
        `3. Where do the documents disagree?`,
      ].join("\n"),
      data: createQuizArtifactData(sources),
    },
    infographic: {
      noteTitle: `Infographic Plan for ${primaryTitle}`,
      preview: `Visual narrative blocks arranged for the uploaded document set.`,
      message: [
        `# Infographic Outline`,
        `Structured a visual summary for **${shortList}**.`,
        ``,
        `- Header: headline insight`,
        `- Middle: three evidence blocks`,
        `- Footer: takeaway and action`,
      ].join("\n"),
      data: createInfographicArtifactData(sources),
    },
    slides: {
      noteTitle: `Slide Deck for ${primaryTitle}`,
      preview: `Presentation arc generated from the selected content.`,
      message: [
        `# Slide Deck Draft`,
        `Organized **${shortList}** into a presentation flow.`,
        ``,
        `1. Title and context`,
        `2. Problem statement`,
        `3. Supporting evidence`,
        `4. Final recommendation`,
      ].join("\n"),
      data: createSlidesArtifactData(sources),
    },
    table: {
      noteTitle: `Data Table for ${primaryTitle}`,
      preview: `Comparison table prepared from the selected sources.`,
      message: [
        `# Data Table`,
        `| Source | Focus | Output |`,
        `| --- | --- | --- |`,
        ...sources.slice(0, 4).map((source) => `| ${source.title} | ${source.type} | Key extracted points |`),
      ].join("\n"),
      data: createTableArtifactData(sources),
    },
  };

  return byTool[tool.id] || {
    noteTitle: `${tool.label} for ${primaryTitle}`,
    preview: `Generated from ${shortList}.`,
    message: `Created a ${tool.label.toLowerCase()} from **${shortList}**.`,
    data: createReportArtifactData(sources),
  };
}

function normalizeGeneratedNote(note) {
  return {
    toolId: "reports",
    artifactData: null,
    ...note,
  };
}

function openArtifactViewer(noteId) {
  const note = state.generatedNotes.find((item) => item.id === noteId);
  if (!note) {
    return;
  }

  state.activeOutputId = note.id;
  elements.viewerTitle.textContent = note.title;
  elements.viewerMeta.textContent = note.meta;
  elements.artifactViewer.classList.remove("is-hidden");
  elements.artifactViewer.setAttribute("aria-hidden", "false");
  renderGeneratedNotes();
  renderArtifactContent(note);
}

function closeArtifactViewer() {
  destroyViewerRuntime();
  elements.viewerBody.innerHTML = "";
  elements.artifactViewer.classList.add("is-hidden");
  elements.artifactViewer.setAttribute("aria-hidden", "true");
}

function renderArtifactContent(note) {
  destroyViewerRuntime();
  elements.viewerBody.innerHTML = "";

  const shell = document.createElement("div");
  shell.className = "artifact-shell";
  elements.viewerBody.appendChild(shell);

  switch (note.toolId) {
    case "mind-map":
      renderMindMapArtifact(shell, note);
      break;
    case "reports":
      renderReportArtifact(shell, note);
      break;
    case "flashcards":
      renderFlashcardsArtifact(shell, note);
      break;
    case "quiz":
      renderQuizArtifact(shell, note);
      break;
    case "infographic":
      renderInfographicArtifact(shell, note);
      break;
    case "slides":
      renderSlidesArtifact(shell, note);
      break;
    case "table":
      renderTableArtifact(shell, note);
      break;
    default:
      renderReportArtifact(shell, note);
      break;
  }
}

function destroyViewerRuntime() {
  if (viewerRuntime.chart) {
    viewerRuntime.chart.destroy();
    viewerRuntime.chart = null;
  }
  if (viewerRuntime.reveal) {
    viewerRuntime.reveal.destroy();
    viewerRuntime.reveal = null;
  }
}

function createMindMapArtifactData(sources) {
  const rootLabel = sources[0]?.title.replace(/\.[^.]+$/, "") || "Workspace Map";
  const keywords = deriveKeywords(sources, 10);
  const branches = [
    { name: "Definitions", children: keywords.slice(0, 3).map((item) => ({ name: item })) },
    { name: "Workflow", children: ["Input", "Retrieval", "Synthesis"].map((item) => ({ name: item })) },
    { name: "Evidence", children: sources.slice(0, 4).map((source) => ({ name: source.title })) },
    { name: "Decisions", children: ["Tradeoffs", "Risks", "Actions"].map((item) => ({ name: item })) },
  ];

  return {
    summary: `Interactive concept map based on ${sources.length} selected source${sources.length === 1 ? "" : "s"}.`,
    root: {
      name: rootLabel,
      children: branches,
    },
    legend: keywords.slice(0, 6),
  };
}

function createReportArtifactData(sources) {
  const labels = sources.map((source) => source.title);
  const themes = deriveKeywords(sources, 12);
  return {
    summary: `Report assembled from ${labels.join(", ")}.`,
    sections: [
      {
        heading: "Executive Summary",
        body: `The selected material points to a shared focus on ${themes.slice(0, 3).join(", ")} with emphasis on consolidating findings into a single decision path.`,
      },
      {
        heading: "Key Findings",
        body: `Across the uploaded sources, the most repeated concerns are ${themes.slice(3, 6).join(", ")}. These items should shape prioritization and follow-up investigation.`,
      },
      {
        heading: "Risks And Constraints",
        body: `The main risks relate to limited coverage across documents, inconsistent terminology, and unknown implementation constraints hidden behind summary titles alone.`,
      },
      {
        heading: "Recommended Next Steps",
        body: `Validate source quality, collect missing evidence, and convert the strongest recurring themes into an implementation checklist before wider distribution.`,
      },
    ],
    highlights: [
      { label: "Sources", value: String(sources.length) },
      { label: "Dominant Theme", value: themes[0] || "Research" },
      { label: "Next Action", value: "Review evidence" },
    ],
  };
}

function createFlashcardsArtifactData(sources) {
  const keywords = deriveKeywords(sources, 8);
  return {
    cards: keywords.slice(0, 6).map((keyword, index) => ({
      front: `Explain how ${keyword} appears in the uploaded material.`,
      back: `Card ${index + 1}: connect ${keyword} to the source titles, define it clearly, and note why it matters to the broader workflow.`,
    })),
  };
}

function createQuizArtifactData(sources) {
  const keywords = deriveKeywords(sources, 9);
  const focus = keywords[0] || "workflow";
  const distractors = ["branding", "packaging", "formatting", "deployment"];
  return {
    questions: [
      {
        prompt: `Which topic is most central across the selected sources?`,
        options: [focus, ...distractors.slice(0, 3)],
        correctIndex: 0,
      },
      {
        prompt: `What should happen immediately after reviewing the selected documents?`,
        options: ["Extract findings and compare them", "Delete the sources", "Ignore overlaps", "Restart the workspace"],
        correctIndex: 0,
      },
      {
        prompt: `Why build artifacts from these documents?`,
        options: ["To turn source material into study and decision outputs", "To remove evidence", "To hide citations", "To reduce source visibility"],
        correctIndex: 0,
      },
    ],
  };
}

function createInfographicArtifactData(sources) {
  const labels = sources.slice(0, 5).map((source) => trimExtension(source.title));
  const values = labels.map((label, index) => Math.max(38, 92 - index * 11));
  const keywords = deriveKeywords(sources, 6);
  return {
    stats: [
      { label: "Sources", value: String(sources.length) },
      { label: "Primary Lens", value: keywords[0] || "Context" },
      { label: "Output", value: "Visual Summary" },
    ],
    chart: { labels, values },
    steps: [
      { title: "Signal", body: `The most visible theme is ${keywords[0] || "evidence synthesis"}.` },
      { title: "Evidence", body: `The selected sources cluster around ${keywords.slice(1, 3).join(" and ") || "shared terminology"}.` },
      { title: "Action", body: `Use the resulting summary to brief collaborators or convert findings into a slide deck.` },
    ],
  };
}

function createSlidesArtifactData(sources) {
  const keywords = deriveKeywords(sources, 8);
  return {
    slides: [
      {
        title: "Source Overview",
        bullets: sources.slice(0, 4).map((source) => `${trimExtension(source.title)} (${source.type})`),
      },
      {
        title: "Key Themes",
        bullets: keywords.slice(0, 4).map((item) => `Theme: ${item}`),
      },
      {
        title: "Findings",
        bullets: [
          "Recurring ideas can be grouped into a consistent narrative",
          "Uploaded sources act as evidence anchors for later Q&A",
          "A structured output is easier to share than raw files",
        ],
      },
      {
        title: "Next Steps",
        bullets: [
          "Validate assumptions with a direct query",
          "Export the deck outline for presentation use",
          "Turn core themes into flashcards or quizzes",
        ],
      },
    ],
  };
}

function createTableArtifactData(sources) {
  const keywords = deriveKeywords(sources, 10);
  return {
    columns: ["Source", "Type", "Focus", "Suggested Output"],
    rows: sources.map((source, index) => ([
      source.title,
      capitalize(source.type),
      keywords[index] || "Synthesis",
      ["Report", "Quiz", "Deck", "Table"][index % 4],
    ])),
    caption: "Structured comparison table built from the currently selected source set.",
  };
}

function renderMindMapArtifact(container, note) {
  const data = note.artifactData || createMindMapArtifactData(getToolContextSources());
  const shell = document.createElement("div");
  shell.className = "mindmap-shell";
  shell.innerHTML = `
    <div class="artifact-block"><p>${data.summary}</p></div>
    <div class="mindmap-legend"></div>
    <svg class="mindmap-svg"></svg>
  `;
  container.appendChild(shell);

  const legend = shell.querySelector(".mindmap-legend");
  (data.legend || []).forEach((item) => {
    const chip = document.createElement("span");
    chip.textContent = item;
    legend.appendChild(chip);
  });

  const svg = d3.select(shell.querySelector(".mindmap-svg"));
  const width = 960;
  const height = 540;
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  const root = d3.hierarchy(data.root);
  const treeLayout = d3.tree().size([height - 80, width - 220]);
  treeLayout(root);

  const graph = svg.append("g").attr("transform", "translate(80, 40)");
  graph.selectAll("path")
    .data(root.links())
    .enter()
    .append("path")
    .attr("fill", "none")
    .attr("stroke", "rgba(16, 163, 127, 0.35)")
    .attr("stroke-width", 2)
    .attr("d", d3.linkHorizontal().x((link) => link.y).y((link) => link.x));

  const node = graph.selectAll("g")
    .data(root.descendants())
    .enter()
    .append("g")
    .attr("transform", (d) => `translate(${d.y},${d.x})`);

  node.append("circle")
    .attr("r", (d) => d.depth === 0 ? 14 : 9)
    .attr("fill", (d) => d.depth === 0 ? "#10a37f" : "#1e1e1e")
    .attr("stroke", "rgba(255,255,255,0.18)")
    .attr("stroke-width", 1.5);

  node.append("text")
    .attr("dx", (d) => d.children ? -14 : 14)
    .attr("dy", 4)
    .attr("text-anchor", (d) => d.children ? "end" : "start")
    .attr("fill", "#ececec")
    .style("font", "13px Manrope")
    .text((d) => d.data.name);
}

function renderReportArtifact(container, note) {
  const data = note.artifactData || createReportArtifactData(getToolContextSources());
  const layout = document.createElement("div");
  layout.className = "report-layout";

  const main = document.createElement("div");
  data.sections.forEach((section) => {
    const block = document.createElement("section");
    block.className = "artifact-block report-section";
    block.innerHTML = `<h4>${section.heading}</h4><p>${section.body}</p>`;
    main.appendChild(block);
  });

  const side = document.createElement("aside");
  side.className = "artifact-block";
  const stats = document.createElement("div");
  stats.className = "artifact-grid";
  data.highlights.forEach((item) => {
    const stat = document.createElement("div");
    stat.className = "artifact-stat";
    stat.innerHTML = `<span class="artifact-stat-label">${item.label}</span><span class="artifact-stat-value">${item.value}</span>`;
    stats.appendChild(stat);
  });
  const list = document.createElement("ul");
  list.className = "report-side-list";
  data.sections.forEach((section) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${section.heading}</strong><span>${section.body}</span>`;
    list.appendChild(li);
  });
  side.appendChild(stats);
  side.appendChild(list);

  layout.appendChild(main);
  layout.appendChild(side);
  container.appendChild(layout);
}

function renderFlashcardsArtifact(container, note) {
  const data = note.artifactData || createFlashcardsArtifactData(getToolContextSources());
  const shell = document.createElement("div");
  shell.innerHTML = `
    <div class="flashcards-toolbar">
      <div>
        <h4>Flashcards</h4>
        <p>Click any card to flip between prompt and answer.</p>
      </div>
      <div class="artifact-chip-row"></div>
    </div>
    <div class="flashcards-grid"></div>
  `;
  container.appendChild(shell);

  const chipRow = shell.querySelector(".artifact-chip-row");
  data.cards.forEach((_, index) => {
    const chip = document.createElement("span");
    chip.className = "artifact-chip";
    chip.textContent = `Card ${index + 1}`;
    chipRow.appendChild(chip);
  });

  const grid = shell.querySelector(".flashcards-grid");
  data.cards.forEach((card, index) => {
    const cardButton = document.createElement("button");
    cardButton.type = "button";
    cardButton.className = "flashcard";
    cardButton.innerHTML = `
      <div class="flashcard-inner">
        <div class="flashcard-face front">
          <span class="flashcard-kicker">Prompt ${index + 1}</span>
          <div class="flashcard-body">${card.front}</div>
          <span class="flashcard-kicker">Click to reveal</span>
        </div>
        <div class="flashcard-face back">
          <span class="flashcard-kicker">Answer</span>
          <div class="flashcard-body">${card.back}</div>
          <span class="flashcard-kicker">Click to return</span>
        </div>
      </div>
    `;
    cardButton.addEventListener("click", () => {
      cardButton.classList.toggle("is-flipped");
    });
    grid.appendChild(cardButton);
  });
}

function renderQuizArtifact(container, note) {
  const data = note.artifactData || createQuizArtifactData(getToolContextSources());
  const shell = document.createElement("div");
  shell.className = "quiz-shell";
  shell.innerHTML = `
    <div class="quiz-header">
      <div>
        <h4>Interactive Quiz</h4>
        <p>Submit the form to score your understanding of the selected material.</p>
      </div>
      <button class="button button-primary" type="button">Grade Quiz</button>
    </div>
    <form class="quiz-form"></form>
    <div class="quiz-result">Choose one answer for each question, then grade the quiz.</div>
  `;
  container.appendChild(shell);

  const form = shell.querySelector(".quiz-form");
  const result = shell.querySelector(".quiz-result");
  const gradeButton = shell.querySelector("button");

  data.questions.forEach((question, questionIndex) => {
    const fieldset = document.createElement("fieldset");
    fieldset.className = "quiz-question";
    fieldset.innerHTML = `<legend class="quiz-question-copy">${question.prompt}</legend>`;

    const options = document.createElement("div");
    options.className = "quiz-options";
    question.options.forEach((option, optionIndex) => {
      const label = document.createElement("label");
      label.className = "quiz-option";
      label.innerHTML = `
        <input type="radio" name="quiz-${questionIndex}" value="${optionIndex}" />
        <span>${option}</span>
      `;
      options.appendChild(label);
    });
    fieldset.appendChild(options);
    form.appendChild(fieldset);
  });

  gradeButton.addEventListener("click", () => {
    let score = 0;
    const questionBlocks = Array.from(form.querySelectorAll(".quiz-question"));
    questionBlocks.forEach((block, index) => {
      const checked = block.querySelector(`input[name="quiz-${index}"]:checked`);
      const optionLabels = Array.from(block.querySelectorAll(".quiz-option"));
      optionLabels.forEach((label) => label.classList.remove("correct", "incorrect"));
      optionLabels[data.questions[index].correctIndex].classList.add("correct");
      if (checked) {
        const chosenIndex = Number(checked.value);
        if (chosenIndex === data.questions[index].correctIndex) {
          score += 1;
        } else {
          optionLabels[chosenIndex].classList.add("incorrect");
        }
      }
    });
    result.textContent = `You scored ${score} out of ${data.questions.length}. Review the highlighted answers and try again if needed.`;
  });
}

function renderInfographicArtifact(container, note) {
  const data = note.artifactData || createInfographicArtifactData(getToolContextSources());
  const shell = document.createElement("div");
  shell.innerHTML = `
    <div class="artifact-grid"></div>
    <div class="infographic-layout">
      <div class="chart-shell"><canvas id="artifact-chart"></canvas></div>
      <div class="infographic-narrative"></div>
    </div>
  `;
  container.appendChild(shell);

  const stats = shell.querySelector(".artifact-grid");
  data.stats.forEach((item) => {
    const stat = document.createElement("div");
    stat.className = "artifact-stat";
    stat.innerHTML = `<span class="artifact-stat-label">${item.label}</span><span class="artifact-stat-value">${item.value}</span>`;
    stats.appendChild(stat);
  });

  const narrative = shell.querySelector(".infographic-narrative");
  data.steps.forEach((step) => {
    const block = document.createElement("div");
    block.className = "infographic-step";
    block.innerHTML = `<h4>${step.title}</h4><p>${step.body}</p>`;
    narrative.appendChild(block);
  });

  const chartCanvas = shell.querySelector("#artifact-chart");
  viewerRuntime.chart = new Chart(chartCanvas, {
    type: "bar",
    data: {
      labels: data.chart.labels,
      datasets: [{
        label: "Signal Strength",
        data: data.chart.values,
        backgroundColor: [
          "rgba(16, 163, 127, 0.85)",
          "rgba(29, 185, 84, 0.72)",
          "rgba(89, 200, 142, 0.64)",
          "rgba(126, 214, 169, 0.58)",
          "rgba(173, 232, 198, 0.5)",
        ],
        borderRadius: 12,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          ticks: { color: "#ececec" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          ticks: { color: "#9a9a9a" },
          grid: { color: "rgba(255,255,255,0.06)" },
        },
      },
    },
  });
}

function renderSlidesArtifact(container, note) {
  const data = note.artifactData || createSlidesArtifactData(getToolContextSources());
  const shell = document.createElement("div");
  shell.className = "slides-shell";
  shell.innerHTML = '<div class="reveal"><div class="slides"></div></div>';
  container.appendChild(shell);

  const slidesNode = shell.querySelector(".slides");
  data.slides.forEach((slide) => {
    const section = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = slide.title;
    const list = document.createElement("ul");
    slide.bullets.forEach((bullet) => {
      const item = document.createElement("li");
      item.textContent = bullet;
      list.appendChild(item);
    });
    section.appendChild(heading);
    section.appendChild(list);
    slidesNode.appendChild(section);
  });

  viewerRuntime.reveal = new Reveal(shell.querySelector(".reveal"), {
    embedded: true,
    controls: true,
    progress: true,
    center: false,
    hash: false,
  });
  viewerRuntime.reveal.initialize();
}

function renderTableArtifact(container, note) {
  const data = note.artifactData || createTableArtifactData(getToolContextSources());
  const shell = document.createElement("div");
  shell.className = "table-shell";
  shell.innerHTML = `
    <p class="table-caption">${data.caption}</p>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead></thead>
        <tbody></tbody>
      </table>
    </div>
  `;
  container.appendChild(shell);

  const thead = shell.querySelector("thead");
  const tbody = shell.querySelector("tbody");
  const headerRow = document.createElement("tr");
  data.columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  data.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function deriveKeywords(sources, limit = 8) {
  const stopWords = new Set(["the", "and", "for", "with", "from", "unit", "notes", "paper", "article", "review", "blog", "research", "documentation", "document", "pdf", "md", "txt", "system"]);
  const counts = new Map();
  sources.forEach((source) => {
    trimExtension(source.title)
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((token) => token.length > 2 && !stopWords.has(token))
      .forEach((token) => {
        counts.set(token, (counts.get(token) || 0) + 1);
      });
  });

  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, limit)
    .map(([token]) => capitalize(token));
}

function trimExtension(value) {
  return value.replace(/\.[^.]+$/, "");
}

function capitalize(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}
