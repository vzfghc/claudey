const state = {
  config: null,
  fields: new Map(),
  localStatus: new Map(),
  modelOptions: [],
  modelComboboxes: new Set(),
  authPollers: new Map(),
  activeView: "providers",
  usageLoaded: false,
};

const MASKED_SECRET = "********";
const VIEW_GROUPS = [
  {
    id: "providers",
    label: "Providers",
    title: "Providers",
    sections: ["providers", "runtime"],
    containerId: "providersSections",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/></svg>`,
  },
  {
    id: "usage",
    label: "Usage",
    title: "Usage",
    sections: [],
    containerId: "usageSections",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 20v-8"/><path d="M12 20V5"/><path d="M19 20v-11"/><path d="M3 20h18"/></svg>`,
  },
  {
    id: "model_config",
    label: "Model Config",
    title: "Model Config",
    sections: ["models", "reasoning", "web_tools"],
    containerId: "modelConfigSections",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h19"/><circle cx="16" cy="7" r="2.5"/><path d="M4 17h19"/><circle cx="10" cy="17" r="2.5"/></svg>`,
  },
  {
    id: "messaging",
    label: "Messaging",
    title: "Messaging",
    sections: ["messaging", "voice"],
    containerId: "messagingSections",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  },
];

const ONBOARDING_DISMISS_KEY = "claudey.onboarding.dismissed";
const ONBOARDING_COMMAND = "hans-claude";

const WELCOME_GREETINGS = [
  "What are we building today, Hans?",
  "Ready to ship something great?",
  "Good to see you. Let’s code.",
  "Your AI command center awaits.",
  "What will you create today?",
  "Back for more? Let’s go.",
  "Engineering mode: on.",
  "The server is yours.",
];

const SIDEBAR_STATE_KEY = "claudey.sidebar.collapsed";

const LOCAL_FIELD_KEYS = {
  lmstudio: "LM_STUDIO_BASE_URL",
  llamacpp: "LLAMACPP_BASE_URL",
  ollama: "OLLAMA_BASE_URL",
};

const ROLE_CARDS = [
  {
    id: "fallback",
    label: "Fallback",
    modelKey: "MODEL",
    reasoningKey: "REASONING_POLICY",
    description: "Default used by Claude Code's /model picker. Roles without an override inherit this.",
    modelLabel: "Model",
  },
  {
    id: "fable",
    label: "Fable",
    modelKey: "MODEL_FABLE",
    reasoningKey: "REASONING_FABLE",
    description: "Override for Fable-tier requests. Empty means use the fallback model.",
    modelLabel: "Model override",
  },
  {
    id: "opus",
    label: "Opus",
    modelKey: "MODEL_OPUS",
    reasoningKey: "REASONING_OPUS",
    description: "Override for Opus-tier requests. Empty means use the fallback model.",
    modelLabel: "Model override",
  },
  {
    id: "sonnet",
    label: "Sonnet",
    modelKey: "MODEL_SONNET",
    reasoningKey: "REASONING_SONNET",
    description: "Override for Sonnet-tier requests. Empty means use the fallback model.",
    modelLabel: "Model override",
  },
  {
    id: "haiku",
    label: "Haiku",
    modelKey: "MODEL_HAIKU",
    reasoningKey: "REASONING_HAIKU",
    description: "Override for Haiku-tier requests. Empty means use the fallback model.",
    modelLabel: "Model override",
  },
];

const ICON_CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5.5"/></svg>`;
const ICON_ALERT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 4L2.5 20h19L12 4z"/><path d="M12 10.5v4" stroke-linecap="round"/><path d="M12 17v.01" stroke-linecap="round"/></svg>`;
const ICON_INFO = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5" stroke-linecap="round"/><path d="M12 8v.01" stroke-linecap="round"/></svg>`;
const ICON_STEP_CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>`;
const ICON_STEP_KEY = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="7.5" cy="15.5" r="4.5"/><path d="M10.7 12.3L20 3"/><path d="M15.5 7.5l2.5 2.5"/><path d="M18 5l1.5 1.5"/></svg>`;
const ICON_STEP_TERMINAL = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3"/><path d="M12 15h5"/></svg>`;
const ICON_CLOSE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
const ICON_SPINNER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9"/></svg>`;

const byId = (id) => document.getElementById(id);

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const SMOOTH_SCROLL = { behavior: REDUCED_MOTION ? "auto" : "smooth" };

function sourceLabel(source) {
  const labels = {
    default: "default",
    template: "template",
    repo_env: "repo .env",
    managed_env: "",
    explicit_env_file: "HANS_ENV_FILE",
    explicit_env_file: "HANS_ENV_FILE",
    process: "process env",
  };
  return Object.prototype.hasOwnProperty.call(labels, source) ? labels[source] : source;
}

function sourceText(field) {
  const parts = [];
  const label = sourceLabel(field.source);
  if (label) {
    parts.push(label);
  }
  if (field.locked) {
    parts.push("locked");
  }
  return parts.join(" ");
}

const LOBEHUB_COLOR_ICONS = new Set([
  "nvidia", "gemini", "vertexai", "deepseek", "mistral", "azure",
  "openrouter", "bedrock", "huggingface", "cohere", "cerebras",
  "cloudflare", "fireworks", "kimi", "minimax", "sambanova",
]);

const LOBEHUB_ID_MAP = {
  nvidia_nim: "nvidia", gemini: "gemini", vertex: "vertexai",
  deepseek: "deepseek", mistral: "mistral", mistral_codestral: "mistral",
  azure_openai: "azure", open_router: "openrouter", bedrock: "bedrock",
  huggingface: "huggingface", cohere: "cohere", cerebras: "cerebras",
  cloudflare: "cloudflare", fireworks: "fireworks", kimi: "kimi",
  kimi_code: "kimi", minimax: "minimax", sambanova: "sambanova",
};

const LOBEHUB_CDN = "https://cdn.jsdelivr.net/npm/@lobehub/icons-static-svg@1.94.0/icons";

function providerLogo(providerId) {
  if (providerId.startsWith("custom_")) {
    const placeholder = document.createElement("span");
    placeholder.className = "provider-logo provider-logo-placeholder";
    placeholder.textContent = "●";
    return placeholder;
  }
  const lobeSlug = LOBEHUB_ID_MAP[providerId];
  const logo = document.createElement("img");
  logo.className = "provider-logo";
  logo.alt = "";
  logo.width = 32;
  logo.height = 32;
  logo.loading = "lazy";

  if (lobeSlug && LOBEHUB_COLOR_ICONS.has(lobeSlug)) {
    logo.src = `${LOBEHUB_CDN}/${lobeSlug}-color.svg`;
  } else {
    logo.src = `/admin/assets/logos/${providerId}.svg`;
  }
  return logo;
}

function statusClass(status) {
  if (["configured", "reachable", "running", "connected"].includes(status)) return "ok";
  if (["missing_key", "missing_config", "missing_url", "unknown", "connecting"].includes(status)) return "warn";
  if (["offline", "error"].includes(status)) return "error";
  return "neutral";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : "";
    } catch {
      // The status remains useful when an upstream proxy returns a non-JSON page.
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

// Warn before closing the page with unsaved changes. Suppressed while the
// apply flow navigates away for an automatic server restart.
let suppressBeforeUnload = false;
window.addEventListener("beforeunload", (event) => {
  if (suppressBeforeUnload) return;
  if (Object.keys(changedValues()).length > 0) {
    event.preventDefault();
    event.returnValue = "";
  }
});

async function load() {
  showMessage("Loading admin config");
  const config = await api("/admin/api/config");
  state.config = config;
  state.fields = new Map(config.fields.map((field) => [field.key, field]));
  // Render the greeting immediately (blinking cursor placeholder) so the
  // topbar always has a component from first paint — nothing else waits on it.
  renderGreeting();
  renderNav();
  renderProviders(config.provider_status);
  renderOnboarding(config.provider_status);
  renderSections(config.sections, config.fields);
  renderServerStatus();
  byId("configPath").textContent = config.paths.managed;
  await refreshConnectedAccounts();
  await renderCombos();
  await hydrateModelOptions();
  await validate(false);
  await refreshLocalStatus();
  updateDirtyState();
  showMessage("");
  // After the dashboard has loaded and settled, fill in the greeting text over
  // the blinking-cursor placeholder that was rendered on first paint.
  animateGreeting();
}

const GREETING_TYPE_MS = 35;
const GREETING_START_DELAY_MS = 120;

// Greeting text is resolved once and reused by both the placeholder and the
// typing phase, so the same greeting is always picked for a given hour.
let greetingText = "";

function pickGreetingText() {
  if (greetingText) return greetingText;
  const seed = Math.floor(Date.now() / 3600000);
  const index = (seed + WELCOME_GREETINGS.length) % WELCOME_GREETINGS.length;
  greetingText = WELCOME_GREETINGS[Math.abs(index)];
  return greetingText;
}

// Phase 1 — render a stable component immediately on first paint: the full text
// for assistive tech plus a blinking cursor placeholder. Nothing else on the
// page waits on the greeting, so the typing can never shift the rest of the UI.
function renderGreeting() {
  const el = byId("welcomeGreeting");
  if (!el) return;
  const text = pickGreetingText();
  el.textContent = "";

  const sr = document.createElement("span");
  sr.className = "sr-only";
  sr.textContent = text;
  el.appendChild(sr);

  const visual = document.createElement("span");
  visual.className = "welcome-greeting-visual";
  visual.setAttribute("aria-hidden", "true");
  el.appendChild(visual);

  if (REDUCED_MOTION || text.length === 0) {
    visual.textContent = text;
    return;
  }

  const cursor = document.createElement("span");
  cursor.className = "typing-cursor";
  cursor.textContent = "|";
  visual.appendChild(cursor);
}

// Phase 2 — type the greeting text into the placeholder after the dashboard has
// settled, keeping the blinking cursor until the text is complete.
function animateGreeting() {
  const el = byId("welcomeGreeting");
  const visual = el && el.querySelector(".welcome-greeting-visual");
  if (!el || !visual) return;
  const text = pickGreetingText();
  if (REDUCED_MOTION || text.length === 0) {
    const settled = visual.querySelector(".typing-cursor");
    if (settled) settled.remove();
    visual.textContent = text;
    return;
  }
  visual.textContent = "";
  const chars = Array.from(text);

  const typed = document.createElement("span");
  typed.className = "welcome-greeting-typed";
  const cursor = document.createElement("span");
  cursor.className = "typing-cursor";
  cursor.textContent = "|";
  visual.append(typed, cursor);

  let index = 0;
  window.setTimeout(function typeNext() {
    if (index < chars.length) {
      typed.textContent = chars.slice(0, index + 1).join("");
      index += 1;
      window.setTimeout(typeNext, GREETING_TYPE_MS);
      return;
    }
    cursor.remove();
  }, GREETING_START_DELAY_MS);
}

function renderNav() {
  const nav = byId("sectionNav");
  nav.innerHTML = "";
  VIEW_GROUPS.forEach((view, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `nav-link${index === 0 ? " active" : ""}`;
    button.dataset.view = view.id;
    button.title = view.label;
    button.style.setProperty("--nav-index", index);
    const icon = document.createElement("span");
    icon.className = "nav-icon";
    icon.innerHTML = view.icon;
    button.appendChild(icon);
    const label = document.createElement("span");
    label.className = "nav-label";
    label.textContent = view.label;
    button.appendChild(label);
    if (index === 0) {
      button.setAttribute("aria-current", "page");
    }
    button.addEventListener("click", () => {
      setActiveView(view.id, { scroll: true });
    });
    nav.appendChild(button);
  });
  setActiveView(state.activeView, { scroll: false });
}

function setActiveView(viewId, { scroll = false } = {}) {
  const activeView =
    VIEW_GROUPS.find((view) => view.id === viewId) || VIEW_GROUPS[0];

  state.activeView = activeView.id;
  byId("pageTitle").textContent = activeView.title;

  document.querySelectorAll(".nav-link").forEach((link) => {
    const selected = link.dataset.view === activeView.id;
    link.classList.toggle("active", selected);
    if (selected) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });

  document.querySelectorAll(".admin-view").forEach((view) => {
    const selected = view.dataset.view === activeView.id;
    view.classList.toggle("active", selected);
    view.hidden = !selected;
  });

  // Ensure tooltip is hidden when not on usage page
  if (activeView.id !== "usage" && usageTooltipEl) {
    usageTooltipEl.hidden = true;
  }

  if (activeView.id === "usage") {
    loadUsage();
  }

  if (scroll) {
    window.scrollTo({ top: 0, ...SMOOTH_SCROLL });
  }
}


const PROVIDER_ORDER_KEY = "claudey.providerOrder";

function _savedOrder() {
  try { return JSON.parse(localStorage.getItem(PROVIDER_ORDER_KEY)) || []; }
  catch { return []; }
}

function _saveOrder(order) {
  localStorage.setItem(PROVIDER_ORDER_KEY, JSON.stringify(order));
}

function _sortedProviders(providers) {
  const order = _savedOrder();
  if (!order.length) return providers;
  const byId = new Map(providers.map((p) => [p.provider_id, p]));
  const ordered = [];
  for (const id of order) {
    if (byId.has(id)) ordered.push(byId.get(id));
    byId.delete(id);
  }
  for (const [, provider] of byId) ordered.push(provider);
  return ordered;
}

function _attachDrag(card, providerId) {
  card.draggable = true;
  card.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", providerId);
    e.dataTransfer.effectAllowed = "move";
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => {
    card.classList.remove("dragging");
    document.querySelectorAll(".provider-card.drag-over").forEach((c) =>
      c.classList.remove("drag-over"),
    );
  });
  card.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (!card.classList.contains("dragging")) {
      card.classList.add("drag-over");
    }
  });
  card.addEventListener("dragleave", () => {
    card.classList.remove("drag-over");
  });
  card.addEventListener("drop", (e) => {
    e.preventDefault();
    card.classList.remove("drag-over");
    const fromId = e.dataTransfer.getData("text/plain");
    if (!fromId || fromId === providerId) return;
    const grid = card.parentNode;
    const fromCard = grid.querySelector(`[data-provider="${fromId}"]`);
    if (!fromCard) return;
    const after = card.nextSibling === fromCard ? card : card.nextSibling;
    grid.insertBefore(fromCard, after);
    const ids = Array.from(grid.querySelectorAll("[data-provider]")).map(
      (c) => c.dataset.provider,
    );
    _saveOrder(ids);
  });
}

function renderProviders(providerStatus) {
  const grid = byId("providerGrid");
  const connectedGrid = byId("connectedAccountGrid");
  grid.innerHTML = "";
  connectedGrid.innerHTML = "";
  const connected = providerStatus.filter(
    (provider) => provider.kind === "connected_account",
  );
  byId("connectedAccountsSection").hidden = connected.length === 0;
  connected.forEach((provider) => {
    const card = renderConnectedAccountCard(provider);
    card.style.setProperty("--card-index", connectedGrid.children.length);
    connectedGrid.appendChild(card);
  });
  _sortedProviders(
    providerStatus.filter((p) => p.kind !== "connected_account"),
  ).forEach((provider) => {
    const card = document.createElement("article");
    card.className = "provider-card";
    card.dataset.provider = provider.provider_id;

    const title = document.createElement("div");
    title.className = "provider-title";
    const logo = providerLogo(provider.provider_id);
    const name = document.createElement("strong");
    name.textContent = provider.display_name || provider.provider_id;
    title.append(logo, name);

    if (provider.kind === "custom") {
      const compatible = document.createElement("span");
      compatible.className = "custom-compatible-badge";
      compatible.textContent =
        provider.compatible === "anthropic" ? "Anthropic" : "OpenAI";
      name.after(compatible);

      const actions = document.createElement("div");
      actions.className = "provider-actions";
      const status = document.createElement("span");
      status.className = "custom-provider-status";
      status.textContent = provider.label || "Configured";
      actions.appendChild(status);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "secondary-button";
      remove.textContent = "Delete";
      remove.addEventListener("click", () => removeCustomProvider(provider));
      actions.appendChild(remove);

      card.append(title, actions);
      card.style.setProperty("--card-index", grid.children.length);
      _attachDrag(card, provider.provider_id);
      grid.appendChild(card);
      return;
    }

    const actions = document.createElement("div");
    actions.className = "provider-actions";

    const isConfigured = ["configured", "reachable"].includes(provider.status);
    const primaryField = providerPrimaryFieldKey(provider);
    const fieldDesc =
      (primaryField && state.fields.get(primaryField)?.description) || "";

    if (isConfigured) {
      const badge = document.createElement("span");
      badge.className = "configured-badge";
      const dot = document.createElement("span");
      dot.className = "configured-dot";
      badge.append(dot, "Configured");
      actions.appendChild(badge);
      const switchBtn = document.createElement("button");
      switchBtn.type = "button";
      switchBtn.className = "secondary-button";
      switchBtn.textContent = "Switch key";
      switchBtn.addEventListener("click", () => scrollToField(primaryField));
      actions.appendChild(switchBtn);
    } else {
      const configure = document.createElement("button");
      configure.type = "button";
      configure.className = "secondary-button card-configure";
      configure.textContent = "Configure";
      configure.addEventListener("click", () => scrollToField(primaryField));
      actions.appendChild(configure);
      const about = document.createElement("button");
      about.type = "button";
      about.className = "secondary-button about-tooltip";
      about.textContent = "About key";
      about.setAttribute(
        "data-tooltip",
        fieldDesc || "No description available.",
      );
      actions.appendChild(about);
    }

    card.append(title, actions);
    card.style.setProperty("--card-index", grid.children.length);
    _attachDrag(card, provider.provider_id);
    grid.appendChild(card);
  });
}

function providerPrimaryFieldKey(provider) {
  if (LOCAL_FIELD_KEYS[provider.provider_id]) {
    return LOCAL_FIELD_KEYS[provider.provider_id];
  }
  if (provider.configuration) {
    const primary = provider.configuration.split(" + ")[0].trim();
    if (primary) return primary;
  }
  return null;
}

function pillForStatus(status) {
  if (["configured", "reachable"].includes(status)) {
    return { className: "ok", label: "Configured" };
  }
  if (["offline", "error"].includes(status)) {
    return { className: "error", label: "Error" };
  }
  return { className: "neutral", label: "Not configured" };
}

function scrollToField(fieldKey) {
  if (!fieldKey) return;
  const input = byId(`field-${fieldKey}`);
  if (!input) return;
  const wrapper = input.closest(".field");
  const section = wrapper?.closest(".settings-section");
  if (
    section &&
    !section.classList.contains("show-advanced") &&
    wrapper?.classList.contains("advanced-field")
  ) {
    section.querySelector(".advanced-toggle")?.click();
  }
  input.scrollIntoView({ ...SMOOTH_SCROLL, block: "center" });
  input.focus({ preventScroll: true });
  }

function renderConnectedAccountCard(provider, status = provider) {
  const card = document.createElement("article");
  card.className = "provider-card";
  card.dataset.provider = provider.provider_id;
  card.dataset.connectedAccount = "true";

  const title = document.createElement("div");
  title.className = "provider-title";
  const nameGroup = document.createElement("span");
  nameGroup.className = "provider-name";
  const name = document.createElement("strong");
  name.textContent = provider.display_name || provider.provider_id;
  nameGroup.append(providerLogo(provider.provider_id), name);
  const pill = document.createElement("span");
  pill.className = `status-pill ${statusClass(status.state || status.status)}`;
  pill.textContent = connectedAccountLabel(status);
  title.append(nameGroup, pill);

  const meta = document.createElement("div");
  meta.className = "provider-meta";
  meta.textContent = connectedAccountMeta(status);

  const actions = document.createElement("div");
  actions.className = "provider-actions";
  populateConnectedAccountActions(provider, status, actions);
  card.append(title, meta, actions);
  return card;
}

function connectedAccountLabel(status) {
  const labels = {
    disconnected: "",
    connecting: "Connecting",
    connected: "",
    error: "Error",
  };
  return labels[status.state] || status.label || "";
}

function connectedAccountMeta(status) {
  if (status.connected) {
    return status.email ? `Connected as ${status.email}` : "Subscription connected";
  }
  if (status.mode === "device" && status.user_code) {
    return status.message || "";
  }
  if (status.state === "connecting") {
    return status.message || "";
  }
  if (status.state === "error") {
    const detail = status.message ? ` - ${status.message}` : "";
    return `Error${detail}`;
  }
  return status.message || "Connect a ChatGPT account.";
}

function populateConnectedAccountActions(provider, status, actions) {
  const providerId = provider.provider_id;
  if (status.state === "connecting") {
    const target = status.authorization_url || status.verification_url;
    if (target) {
      actions.appendChild(authButton("Open sign-in", () => window.open(target, "_blank", "noopener")));
    }
    if (status.mode === "device" && status.user_code) {
      actions.appendChild(
        authButton(
          "Copy code",
          () => copyDeviceCode(status.user_code),
          "secondary-button",
        ),
      );
    }
    actions.appendChild(
      authButton("Cancel", () => cancelConnectedAccountLogin(providerId), "secondary-button"),
    );
    return;
  }
  if (status.connected) {
    if (providerId === "anthropic") {
      const badge = document.createElement("span");
      badge.className = "configured-badge";
      const dot = document.createElement("span");
      dot.className = "configured-dot";
      badge.append(dot, "Configured");
      actions.appendChild(badge);
      actions.appendChild(
        authButton("Switch key", () => scrollToField("ANTHROPIC_AUTH_TOKEN"), "secondary-button"),
      );
      return;
    }
    actions.appendChild(
      authButton(
        "Reconnect",
        (button) => startConnectedAccountLogin(providerId, "browser", button),
      ),
    );
    actions.appendChild(
      authButton(
        "Disconnect",
        () => disconnectConnectedAccount(providerId),
        "secondary-button",
      ),
    );
    return;
  }
  // Anthropic has no OAuth flow — "Connect" scrolls to the API key field.
  if (providerId === "anthropic") {
    actions.appendChild(
      authButton("Configure", (button) => scrollToField("ANTHROPIC_AUTH_TOKEN")),
    );
    return;
  }
  actions.appendChild(
    authButton("Connect", (button) => startConnectedAccountLogin(providerId, "browser", button)),
    authButton(
      "Use device code",
      (button) => startConnectedAccountLogin(providerId, "device", button),
      "secondary-button",
    ),
  );
}

function authButton(label, action, className = "secondary-button card-configure") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", () => action(button));
  return button;
}

async function refreshConnectedAccounts() {
  const providers = (state.config?.provider_status || []).filter(
    (provider) => provider.kind === "connected_account",
  );
  await Promise.all(
    providers.map(async (provider) => {
      try {
        const status = await api(`/admin/api/providers/${provider.provider_id}/auth`);
        updateConnectedAccountCard(provider, status);
        if (status.state === "connecting") pollConnectedAccount(provider);
      } catch (error) {
        updateConnectedAccountCard(provider, {
          state: "error",
          connected: false,
          message: error.message,
        });
      }
    }),
  );
}

function updateConnectedAccountCard(provider, status) {
  const current = document.querySelector(
    `[data-provider="${provider.provider_id}"][data-connected-account="true"]`,
  );
  if (current) current.replaceWith(renderConnectedAccountCard(provider, status));
}

async function startConnectedAccountLogin(providerId, mode, button) {
  button.disabled = true;
  const popup = window.open("about:blank", "_blank");
  if (popup) popup.opener = null;
  try {
    const status = await api(`/admin/api/providers/${providerId}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    const provider = connectedAccountDescriptor(providerId);
    updateConnectedAccountCard(provider, status);
    pollConnectedAccount(provider);
    const target = status.authorization_url || status.verification_url;
    try {
      if (target && popup && !popup.closed) {
        popup.location.replace(target);
      } else if (target) {
        window.open(target, "_blank", "noopener");
      } else if (popup && !popup.closed) {
        popup.close();
      }
    } catch {
      // Popup closed or blocked - login already started, card handles recovery
    }
  } catch (error) {
    if (popup) popup.close();
    showMessage(error.message, true);
    button.disabled = false;
  }
}

async function cancelConnectedAccountLogin(providerId) {
  clearConnectedAccountPoll(providerId);
  const status = await api(`/admin/api/providers/${providerId}/auth/cancel`, {
    method: "POST",
  });
  updateConnectedAccountCard(connectedAccountDescriptor(providerId), status);
}

async function disconnectConnectedAccount(providerId) {
  if (!window.confirm("Disconnect this ChatGPT account from Claudey?")) return;
  clearConnectedAccountPoll(providerId);
  const status = await api(`/admin/api/providers/${providerId}/auth`, {
    method: "DELETE",
  });
  updateConnectedAccountCard(connectedAccountDescriptor(providerId), status);
  await hydrateModelOptions();
}

async function pollConnectedAccount(provider) {
  clearConnectedAccountPoll(provider.provider_id);
  const poll = async () => {
    try {
      const status = await api(`/admin/api/providers/${provider.provider_id}/auth`);
      updateConnectedAccountCard(provider, status);
      if (status.state === "connecting") {
        state.authPollers.set(provider.provider_id, window.setTimeout(poll, 1000));
      } else {
        state.authPollers.delete(provider.provider_id);
        if (status.connected) await hydrateModelOptions();
      }
    } catch (error) {
      state.authPollers.delete(provider.provider_id);
      showMessage(error.message, true);
    }
  };
  state.authPollers.set(provider.provider_id, window.setTimeout(poll, 1000));
}

function clearConnectedAccountPoll(providerId) {
  const timer = state.authPollers.get(providerId);
  if (timer) window.clearTimeout(timer);
  state.authPollers.delete(providerId);
}

function connectedAccountDescriptor(providerId) {
  return state.config.provider_status.find(
    (provider) => provider.provider_id === providerId,
  );
}

async function copyDeviceCode(code) {
  try {
    await navigator.clipboard.writeText(code);
    showMessage("Device code copied.");
  } catch {
    showMessage(`Copy this device code: ${code}`);
  }
}

function setCardPill(card, status, label, pulsing = false) {
  const pill = card.querySelector(".status-pill");
  if (!pill) return;
  pill.className = `status-pill ${statusClass(status)}${pulsing ? " pulsing" : ""}`;
  pill.textContent = label;
}

function updateProviderCard(providerId, status, label, metaText, pulsing = false) {
  const card = document.querySelector(`[data-provider="${providerId}"]`);
  if (!card) return;
  const pillState = pillForStatus(status);
  setCardPill(card, status, pulsing ? label : pillState.label, pulsing);
  if (metaText) {
    const meta = card.querySelector(".provider-meta");
    if (meta) meta.textContent = metaText;
  }
}

function renderSections(sections, fields) {
  state.modelComboboxes.clear();
  VIEW_GROUPS.forEach((view) => {
    byId(view.containerId).innerHTML = "";
  });

  const sectionById = new Map(sections.map((section) => [section.id, section]));
  const bySection = new Map();
  sections.forEach((section) => bySection.set(section.id, []));
  fields.forEach((field) => {
    if (!bySection.has(field.section)) bySection.set(field.section, []);
    bySection.get(field.section).push(field);
  });

  VIEW_GROUPS.forEach((view) => {
    const container = byId(view.containerId);
    view.sections.forEach((sectionId) => {
      const section = sectionById.get(sectionId);
      const sectionFields = bySection.get(sectionId) || [];
      if (!section || sectionFields.length === 0) return;

      const sectionEl = document.createElement("section");
      sectionEl.className = "settings-section";
      sectionEl.id = `section-${section.id}`;

      const heading = document.createElement("div");
      heading.className = "section-heading";
      heading.innerHTML = `<div><h3>${section.label}</h3><p>${section.description}</p></div>`;
      if (section.id === "models") {
        const refreshButton = document.createElement("button");
        refreshButton.type = "button";
        refreshButton.className = "secondary-button";
        refreshButton.textContent = "Refresh models";
        refreshButton.addEventListener("click", () => refreshModelOptions(refreshButton));
        heading.appendChild(refreshButton);
      }
      if (section.id === "voice") {
        heading.querySelector("h3").textContent = "Voice notes";
        heading.classList.add("subheading");
      }
      sectionEl.appendChild(heading);

      if (section.id === "models") {
        sectionEl.appendChild(renderModelRoleCards(sectionFields, bySection));
      } else {
        const grid = document.createElement("div");
        grid.className = "field-grid";
        sectionFields.forEach((field) => {
          grid.appendChild(renderField(field));
        });
        sectionEl.appendChild(grid);
      }

      if (sectionFields.some((field) => field.advanced)) {
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "ghost-button advanced-toggle";
        toggle.textContent = "Show advanced";
        toggle.addEventListener("click", () => {
          const showing = sectionEl.classList.toggle("show-advanced");
          toggle.textContent = showing ? "Hide advanced" : "Show advanced";
        });
        sectionEl.appendChild(toggle);
      }

      container.appendChild(sectionEl);
    });
  });
}

function renderModelRoleCards(modelFields, bySection) {
  const modelByKey = new Map(modelFields.map((field) => [field.key, field]));
  const reasoningByKey = new Map(
    (bySection.get("reasoning") || []).map((field) => [field.key, field]),
  );
  const wrapper = document.createElement("div");
  wrapper.className = "role-card-grid";
  ROLE_CARDS.forEach((role) => {
    const card = document.createElement("article");
    card.className = "role-card";
    card.id = `role-card-${role.id}`;

    const header = document.createElement("header");
    header.className = "role-card-header";
    const title = document.createElement("h4");
    title.textContent = role.label;
    const description = document.createElement("p");
    description.textContent = role.description;
    header.append(title, description);
    card.appendChild(header);

    const body = document.createElement("div");
    body.className = "role-card-body";
    const modelField = modelByKey.get(role.modelKey);
    if (modelField) {
      body.appendChild(
        renderField({ ...modelField, label: role.modelLabel }, { showReset: true }),
      );
    }
    const reasoningField = reasoningByKey.get(role.reasoningKey);
    if (reasoningField) {
      body.appendChild(
        renderField({ ...reasoningField, label: "Reasoning policy" }),
      );
    }
    card.appendChild(body);
    wrapper.appendChild(card);
  });
  return wrapper;
}

function renderField(field, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `field${field.advanced ? " advanced-field" : ""}`;
  wrapper.dataset.key = field.key;

  const label = document.createElement("label");
  label.htmlFor = `field-${field.key}`;
  const labelText = document.createElement("span");
  labelText.textContent = field.label;
  label.appendChild(labelText);

  const source = sourceText(field);
  if (source) {
    const sourceEl = document.createElement("span");
    sourceEl.className = "field-source";
    sourceEl.textContent = source;
    label.appendChild(sourceEl);
  }

  const input = inputForField(field);
  input.id = `field-${field.key}`;
  input.dataset.key = field.key;
  input.dataset.original = field.value || "";
  input.dataset.secret = field.secret ? "true" : "false";
  input.dataset.configured = field.configured ? "true" : "false";
  input.dataset.fieldType = field.type;
  input.disabled = field.locked;
  input.addEventListener("input", updateDirtyState);
  input.addEventListener("change", updateDirtyState);
  if (field.type === "optional_model") {
    input.addEventListener("blur", () => {
      if (!input.value.trim() || input.value.trim().toLowerCase() === "none") {
        input.value = "None";
        updateDirtyState();
      }
    });
  }

  const control = platformSegments(field, input, options) ||
    (field.type === "model" || field.type === "optional_model"
      ? new ModelCombobox(input, field).element
      : input);

  if (options.showReset) {
    const row = document.createElement("div");
    row.className = "field-label-row";
    row.append(label, fieldResetButton(field, input));
    wrapper.append(row, control);
  } else {
    wrapper.append(label, control);
  }
  if (field.type === "optional_model") {
    const hint = document.createElement("div");
    hint.className = "field-default-hint";
    hint.textContent = "Uses provider default";
    const updateHint = () => {
      const empty =
        !input.value.trim() || input.value.trim().toLowerCase() === "none";
      hint.hidden = !empty;
    };
    input.addEventListener("input", updateHint);
    updateHint();
    wrapper.appendChild(hint);
  }
  return wrapper;
}

function platformSegments(field, input, options) {
  if (field.key !== "MESSAGING_PLATFORM" || options?.segments === false) return null;
  const wrapper = document.createElement("div");
  wrapper.className = "segment-field";

  const group = document.createElement("div");
  group.className = "segmented-control";
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", field.label);

  const order = { discord: 0, telegram: 1, none: 2 };
  const optionsList = [...(field.options || [])].sort(
    (left, right) => (order[left.value] ?? 9) - (order[right.value] ?? 9),
  );
  const selectedValue = field.value || optionsList[0]?.value || "";
  const segments = [];
  optionsList.forEach((item, index) => {
    const segment = document.createElement("button");
    segment.type = "button";
    segment.setAttribute("role", "radio");
    segment.setAttribute("aria-checked", String(item.value === selectedValue));
    segment.tabIndex = item.value === selectedValue ? 0 : -1;
    segment.className = "segment";
    segment.dataset.value = item.value;
    segment.disabled = field.locked;
    segment.append(platformLetterIcon(item.value));
    const label = document.createElement("span");
    label.textContent = item.label.charAt(0).toUpperCase() + item.label.slice(1);
    segment.appendChild(label);

    const select = (focus) => {
      input.value = segment.dataset.value;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      updateDirtyState();
      segments.forEach((candidate) => {
        const selected = candidate === segment;
        candidate.setAttribute("aria-checked", String(selected));
        candidate.tabIndex = selected ? 0 : -1;
      });
      if (focus) segment.focus();
    };

    segment.addEventListener("click", () => {
      if (!segment.disabled && segment.dataset.value !== input.value) select(false);
    });
    segment.addEventListener("keydown", (event) => {
      let next = null;
      if (event.key === "ArrowRight") next = (index + 1) % segments.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + segments.length) % segments.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = segments.length - 1;
      else return;
      event.preventDefault();
      if (next !== index) {
        segments[next].click();
        segments[next].focus();
      }
    });
    segments.push(segment);
    group.appendChild(segment);
  });

  input.hidden = true;
  wrapper.append(input, group);
  return wrapper;
}

function platformLetterIcon(value) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "14");
  svg.setAttribute("height", "14");
  svg.setAttribute("aria-hidden", "true");
  if (value === "none") {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", "8");
    circle.setAttribute("cy", "8");
    circle.setAttribute("r", "5.5");
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", "currentColor");
    circle.setAttribute("stroke-width", "1.5");
    const slash = document.createElementNS("http://www.w3.org/2000/svg", "path");
    slash.setAttribute("d", "M5 5l6 6");
    slash.setAttribute("stroke", "currentColor");
    slash.setAttribute("stroke-width", "1.5");
    svg.append(circle, slash);
    return svg;
  }
  const bubble = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bubble.setAttribute("x", "1");
  bubble.setAttribute("y", "2.5");
  bubble.setAttribute("width", "14");
  bubble.setAttribute("height", "9.5");
  bubble.setAttribute("rx", "3");
  bubble.setAttribute("fill", "currentColor");
  const letter = document.createElementNS("http://www.w3.org/2000/svg", "text");
  letter.setAttribute("x", "8");
  letter.setAttribute("y", "10.1");
  letter.setAttribute("text-anchor", "middle");
  letter.setAttribute("font-size", "7.5");
  letter.setAttribute("font-weight", "700");
  letter.setAttribute("fill", "#ffffff");
  letter.textContent = value === "discord" ? "D" : "T";
  svg.append(bubble, letter);
  return svg;
}

function fieldResetButton(field, input) {
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "field-reset";
  reset.textContent = "Reset";
  reset.setAttribute("aria-label", `Reset ${field.label}`);
  reset.addEventListener("click", (event) => {
    event.preventDefault();
    if (field.type === "optional_model") {
      input.value = "None";
    } else if (field.type === "select") {
      input.value = field.options[0]?.value || "";
    } else if (input.type === "checkbox") {
      input.checked = false;
    } else {
      input.value = "";
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    updateDirtyState();
    input.focus({ preventScroll: true });
  });
  return reset;
}

function inputForField(field) {
  if (field.type === "boolean") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = String(field.value).toLowerCase() === "true";
    input.dataset.original = input.checked ? "true" : "false";
    return input;
  }

  if (field.type === "select") {
    const select = document.createElement("select");
    field.options.forEach((item) =>
      select.appendChild(option(item.value, item.label)),
    );
    select.value = field.value || field.options[0]?.value || "";
    return select;
  }

  if (field.type === "textarea") {
    const textarea = document.createElement("textarea");
    textarea.value = field.value || "";
    return textarea;
  }

  if (field.type === "model" || field.type === "optional_model") {
    const input = document.createElement("input");
    input.type = "text";
    input.value = field.value || (field.type === "optional_model" ? "None" : "");
    input.autocomplete = "off";
    input.placeholder =
      field.type === "optional_model"
        ? "Uses provider default"
        : "Search or enter provider/model";
    return input;
  }

  const input = document.createElement("input");
  input.type = field.type === "number" ? "number" : "text";
  if (field.type === "secret") {
    input.type = "password";
    input.placeholder = field.configured
      ? "Configured - enter a new value to replace"
      : "Not configured";
    input.value = "";
    input.autocomplete = "off";
  } else {
    input.value = field.value || "";
  }
  return input;
}

class ModelCombobox {
  constructor(input, field) {
    this.input = input;
    this.fieldType = field.type;
    this.activeIndex = -1;
    this.query = "";

    this.element = document.createElement("div");
    this.element.className = "model-combobox";
    this.listbox = document.createElement("div");
    this.listbox.className = "model-combobox-list";
    this.listbox.id = `model-options-${field.key}`;
    this.listbox.setAttribute("role", "listbox");
    this.listbox.hidden = true;
    this.toggle = document.createElement("button");
    this.toggle.type = "button";
    this.toggle.className = "model-combobox-toggle";
    this.toggle.disabled = input.disabled;
    this.toggle.setAttribute("aria-label", `Show ${field.label} options`);

    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-haspopup", "listbox");
    for (const control of [input, this.toggle]) {
      control.setAttribute("aria-controls", this.listbox.id);
      control.setAttribute("aria-expanded", "false");
    }

    input.addEventListener("click", () => this.open());
    // Pre-filled values (configured model, "None" for optional fields) would
    // otherwise get typed characters appended, so filtering could never match.
    // Select the whole value on focus so the first keystroke replaces it.
    input.addEventListener("focus", () => this.input.select());
    input.addEventListener("input", () => this.open(input.value));
    input.addEventListener("keydown", (event) => this.handleKeydown(event));
    this.toggle.addEventListener("mousedown", (event) => event.preventDefault());
    this.toggle.addEventListener("click", () => {
      if (this.isOpen) this.close();
      else this.open();
      input.focus();
    });
    this.listbox.addEventListener("mousedown", (event) => event.preventDefault());
    this.listbox.addEventListener("mousemove", (event) => {
      const optionEl = event.target.closest('[role="option"]');
      if (optionEl) this.setActive(this.visibleOptions.indexOf(optionEl));
    });
    this.listbox.addEventListener("click", (event) => {
      const optionEl = event.target.closest('[role="option"]');
      if (optionEl) this.select(optionEl.dataset.value);
    });

    this.element.append(input, this.toggle, this.listbox);
    state.modelComboboxes.add(this);
  }

  get isOpen() {
    return this.element.classList.contains("open");
  }

  get values() {
    return this.fieldType === "optional_model"
      ? ["None", ...state.modelOptions]
      : state.modelOptions;
  }

  get visibleOptions() {
    return Array.from(this.listbox.querySelectorAll('[role="option"]'));
  }

  open(query = "") {
    if (this.input.disabled) return;
    state.modelComboboxes.forEach((combobox) => {
      if (combobox !== this) combobox.close();
    });
    this.render(query);
    this.element.classList.add("open");
    this.listbox.hidden = false;
    this.setExpanded(true);
  }

  close() {
    this.element.classList.remove("open");
    this.listbox.hidden = true;
    this.activeIndex = -1;
    this.input.removeAttribute("aria-activedescendant");
    this.setExpanded(false);
  }

  setExpanded(expanded) {
    for (const control of [this.input, this.toggle]) {
      control.setAttribute("aria-expanded", String(expanded));
    }
  }

  render(query) {
    this.query = query;
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const values = normalizedQuery
      ? this.values.filter((value) =>
          value.toLocaleLowerCase().includes(normalizedQuery),
        )
      : this.values;
    this.listbox.innerHTML = "";

    if (values.length === 0) {
      const empty = document.createElement("div");
      empty.className = "model-combobox-empty";
      empty.textContent = state.modelOptions.length
        ? "No matching models. You can still enter a custom slug."
        : "No discovered models. Refresh models or enter a custom slug.";
      this.listbox.appendChild(empty);
      this.activeIndex = -1;
      this.input.removeAttribute("aria-activedescendant");
      return;
    }

    values.forEach((value, index) => {
      const optionEl = document.createElement("div");
      optionEl.className = "model-combobox-option";
      optionEl.id = `${this.listbox.id}-option-${index}`;
      optionEl.dataset.value = value;
      optionEl.setAttribute("role", "option");
      optionEl.textContent = value;
      this.listbox.appendChild(optionEl);
    });
    const selectedIndex = values.indexOf(this.input.value);
    this.setActive(selectedIndex >= 0 ? selectedIndex : 0, false);
  }

  setActive(index, scroll = true) {
    const options = this.visibleOptions;
    if (options.length === 0) return;
    this.activeIndex = Math.max(0, Math.min(index, options.length - 1));
    options.forEach((optionEl, optionIndex) => {
      const active = optionIndex === this.activeIndex;
      optionEl.classList.toggle("active", active);
      optionEl.setAttribute("aria-selected", String(active));
    });
    const activeOption = options[this.activeIndex];
    this.input.setAttribute("aria-activedescendant", activeOption.id);
    if (scroll) activeOption.scrollIntoView({ block: "nearest" });
  }

  move(offset) {
    const count = this.visibleOptions.length;
    if (count) this.setActive((this.activeIndex + offset + count) % count);
  }

  select(value) {
    this.input.value = value;
    this.input.dispatchEvent(new Event("change", { bubbles: true }));
    this.close();
    this.input.focus();
  }

  handleKeydown(event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (this.isOpen) {
        this.move(event.key === "ArrowDown" ? 1 : -1);
      } else {
        this.open();
        if (event.key === "ArrowUp") {
          this.setActive(this.visibleOptions.length - 1);
        }
      }
    } else if (this.isOpen && (event.key === "Home" || event.key === "End")) {
      event.preventDefault();
      this.setActive(event.key === "Home" ? 0 : this.visibleOptions.length - 1);
    } else if (this.isOpen && event.key === "Enter") {
      const active = this.visibleOptions[this.activeIndex];
      if (active) {
        event.preventDefault();
        this.select(active.dataset.value);
      }
    } else if (this.isOpen && event.key === "Escape") {
      event.preventDefault();
      this.close();
    } else if (this.isOpen && event.key === "Tab") {
      this.close();
    }
  }
}

function option(value, label) {
  const optionEl = document.createElement("option");
  optionEl.value = value;
  optionEl.textContent = label;
  return optionEl;
}

function readFieldValue(input) {
  if (input.type === "checkbox") return input.checked ? "true" : "false";
  if (
    input.dataset.fieldType === "optional_model" &&
    input.value.trim().toLowerCase() === "none"
  ) {
    return "";
  }
  if (input.dataset.secret === "true" && input.dataset.configured === "true") {
    return input.value ? input.value : MASKED_SECRET;
  }
  return input.value;
}

function changedValues() {
  const values = {};
  document.querySelectorAll("[data-key]").forEach((input) => {
    if (input.disabled || !input.matches("input, select, textarea")) return;
    const value = readFieldValue(input);
    if (value !== input.dataset.original) {
      values[input.dataset.key] = value;
    }
  });
  return values;
}

function updateDirtyState() {
  const count = Object.keys(changedValues()).length;
  byId("dirtyState").textContent =
    count === 0 ? "No changes" : `${count} unsaved change${count === 1 ? "" : "s"}`;
  byId("applyButton").disabled = count === 0;
}

async function validate(showResult = true) {
  const result = await api("/admin/api/config/validate", {
    method: "POST",
    body: JSON.stringify({ values: changedValues() }),
  });
  if (showResult) {
    showValidationResult(result);
  }
  return result;
}

function showValidationResult(result) {
  if (result.valid) {
    showMessage("Config shape is valid", "ok");
  } else {
    showMessage(result.errors.join("; "), "error");
  }
}

async function apply() {
  const result = await api("/admin/api/config/apply", {
    method: "POST",
    body: JSON.stringify({ values: changedValues() }),
  });
  if (!result.applied) {
    showValidationResult(result);
    return;
  }
  const restart = result.restart || {};
  if (restart.required && restart.automatic) {
    showMessage("Applied. Restarting server...", "loading");
    byId("applyButton").disabled = true;
    suppressBeforeUnload = true;
    setTimeout(() => {
      window.location.href = restart.admin_url || "/admin";
    }, 1600);
    return;
  }
  const pending = restart.required ? restart.fields || [] : result.pending_fields || [];
  await load();
  showMessage(
    pending.length
      ? `Applied. Restart hans-server to use: ${pending.join(", ")}`
      : "Applied",
    "ok",
  );
}

async function restartServer() {
  const button = byId("restartButton");
  button.disabled = true;
  try {
    const result = await api("/admin/api/restart", { method: "POST" });
    showMessage("Restarting server...", "loading");
    suppressBeforeUnload = true;
    setTimeout(() => {
      window.location.href = result.admin_url || "/admin";
    }, 1600);
  } catch (error) {
    button.disabled = false;
    showMessage(`Restart failed: ${error.message}`, "error");
  }
}

async function refreshLocalStatus() {
  (state.config?.provider_status || [])
    .filter((provider) => provider.kind === "local")
    .forEach((provider) => {
      const card = document.querySelector(`[data-provider="${provider.provider_id}"]`);
      if (card) setCardPill(card, "unknown", "Validating…", true);
    });
  const result = await api("/admin/api/providers/local-status");
  result.providers.forEach((provider) => {
    state.localStatus.set(provider.provider_id, provider);
    const meta = provider.status_code
      ? `${provider.base_url} returned HTTP ${provider.status_code}`
      : provider.base_url;
    updateProviderCard(provider.provider_id, provider.status, provider.label, meta);
  });
}

async function testProvider(providerId, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Testing";
  const card = document.querySelector(`[data-provider="${providerId}"]`);
  if (card) setCardPill(card, "unknown", "Validating…", true);
  try {
    const result = await api(`/admin/api/providers/${providerId}/test`, {
      method: "POST",
      body: "{}",
    });
    if (result.ok) {
      updateProviderCard(
        providerId,
        "reachable",
        `${result.models.length} models`,
        result.models.slice(0, 3).join(", ") || "No models returned",
      );
      setModelOptions([
        ...state.modelOptions,
        ...result.models.map((model) => `${providerId}/${model}`),
      ]);
    } else {
      updateProviderCard(providerId, "offline", result.error_type, result.error_type);
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function hydrateModelOptions() {
  try {
    await loadModelOptions();
  } catch {
    // Model fields remain editable when optional catalog hydration is unavailable.
  }
}

async function loadModelOptions(refresh = false) {
  const result = await api("/admin/api/models" + (refresh ? "/refresh" : ""), {
    method: refresh ? "POST" : "GET",
  });
  setModelOptions(result.models);
  return result;
}

async function refreshModelOptions(button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Refreshing";
  showMessage("Refreshing models...", "loading");
  try {
    const result = await loadModelOptions(true);
    const failedProviders = result.failed_providers || [];
    if (failedProviders.length) {
      const labels = failedProviders.map(providerDisplayName).join(", ");
      showMessage(
        `${state.modelOptions.length} models available; could not refresh ${labels}`,
        "warn",
      );
    } else {
      showMessage(`${state.modelOptions.length} models available`, "ok");
    }
  } catch (error) {
    showMessage(`Could not refresh models: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function providerDisplayName(providerId) {
  const provider = state.config?.provider_status?.find(
    (candidate) => candidate.provider_id === providerId,
  );
  return provider?.display_name || providerId;
}

function setModelOptions(models) {
  state.modelOptions = Array.from(
    new Set(models.filter((model) => typeof model === "string" && model.trim())),
  ).sort((left, right) => left.localeCompare(right));
  state.modelComboboxes.forEach((combobox) => {
    if (combobox.isOpen) combobox.render(combobox.query);
  });
}

function showMessage(message, kind = "") {
  const area = byId("messageArea");
  area.textContent = message;
  area.className = `message-area ${kind}`.trim();
  if (message) showToast(message, kind);
}

function showToast(message, kind = "") {
  const container = byId("toastContainer");
  if (!container) return;
  // A pending loading toast is superseded, not stacked.
  container.querySelector(".toast-loading")?.remove();
  const toast = document.createElement("div");
  toast.className = `toast${kind ? ` toast-${kind}` : ""}`;
  toast.setAttribute("role", "status");
  const icon = document.createElement("span");
  icon.className = "toast-icon";
  icon.innerHTML =
    kind === "ok" ? ICON_CHECK : kind === "error" ? ICON_ALERT : kind === "loading" ? ICON_SPINNER : ICON_INFO;
  const text = document.createElement("span");
  text.className = "toast-text";
  text.textContent = message;
  toast.append(icon, text);
  container.appendChild(toast);
  const remove = () => {
    toast.classList.add("toast-leaving");
    window.setTimeout(() => toast.remove(), 200);
  };
  toast.addEventListener("click", remove);
  if (kind !== "loading") {
    window.setTimeout(remove, 4000);
  }
}

function renderOnboarding(providerStatus) {
  const container = byId("onboardingCard");
  container.innerHTML = "";
  const hasConfigured = providerStatus.some(
    (provider) =>
      ["configured", "reachable"].includes(provider.status),
  );
  if (hasConfigured) {
    localStorage.removeItem(ONBOARDING_DISMISS_KEY);
    container.hidden = true;
    return;
  }
  if (localStorage.getItem(ONBOARDING_DISMISS_KEY)) {
    container.hidden = true;
    return;
  }
  container.hidden = false;

  const header = document.createElement("header");
  header.className = "onboarding-header";
  const titleGroup = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = "Welcome to Claudey — get set up in a minute";
  const subtitle = document.createElement("p");
  subtitle.textContent =
    "Connect any OpenAI-compatible provider, then start coding with hans-claude.";
  titleGroup.append(title, subtitle);
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "ghost-button onboarding-dismiss";
  dismiss.setAttribute("aria-label", "Dismiss onboarding guide");
  dismiss.innerHTML = ICON_CLOSE;
  dismiss.addEventListener("click", () => {
    localStorage.setItem(ONBOARDING_DISMISS_KEY, "1");
    container.hidden = true;
  });
  header.append(titleGroup, dismiss);

  const steps = document.createElement("ol");
  steps.className = "onboarding-steps";
  const stepContent = [
    {
      icon: ICON_STEP_CHECK,
      title: "Pick a provider",
      body: "Choose one from the grid below — NVIDIA NIM, OpenRouter, DeepSeek and 30+ more.",
    },
    {
      icon: ICON_STEP_KEY,
      title: "Paste your API key and Apply",
      body: "Keys are stored in your local .env file. Apply with the button below or Ctrl+Enter.",
    },
    {
      icon: ICON_STEP_TERMINAL,
      title: "Run hans-claude",
      body: "Start a coding session with the same providers you just configured:",
    },
  ];
  stepContent.forEach((step, index) => {
    const item = document.createElement("li");
    item.className = "onboarding-step";
    const icon = document.createElement("span");
    icon.className = "step-icon";
    icon.innerHTML = step.icon;
    const text = document.createElement("div");
    const stepNum = document.createElement("span");
    stepNum.className = "step-num";
    stepNum.textContent = `Step ${index + 1}`;
    const stepTitle = document.createElement("strong");
    stepTitle.textContent = step.title;
    const stepBody = document.createElement("p");
    stepBody.textContent = step.body;
    text.append(stepNum, stepTitle, stepBody);
    if (index === 2) {
      const command = document.createElement("div");
      command.className = "command-pill";
      const code = document.createElement("code");
      code.textContent = ONBOARDING_COMMAND;
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "copy-command";
      copy.textContent = "Copy";
      copy.addEventListener("click", () => copyOnboardingCommand(copy));
      command.append(code, copy);
      stepBody.after(command);
    }
    item.append(icon, text);
    steps.appendChild(item);
  });

  container.append(header, steps);
}

async function copyOnboardingCommand(button) {
  const command = ONBOARDING_COMMAND;
  try {
    await navigator.clipboard.writeText(command);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = command;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  button.textContent = "Copied!";
  button.classList.add("copied");
  showToast(`${command} copied to clipboard`, "ok");
  window.setTimeout(() => {
    button.textContent = "Copy";
    button.classList.remove("copied");
  }, 2000);
}

async function renderServerStatus() {
  const pill = byId("serverStatusPill");
  if (!pill) return;
  pill.className = "server-status checking";
  pill.innerHTML =
    '<span class="status-dot"></span><span class="status-text">Checking…</span>';
  try {
    const status = await api("/admin/api/status");
    if (status.status === "running") {
      const version = status.version ? ` v${status.version}` : "";
      pill.className = "server-status ok rainbow";
      pill.innerHTML = `<span class="status-dot"></span><span class="status-text">Running on :${status.port ?? ""}${version}</span>`;
    } else {
      pill.className = "server-status stopped";
      pill.innerHTML = '<span class="status-dot"></span><span class="status-text">Stopped</span>';
    }
  } catch {
    pill.className = "server-status fallback";
    pill.textContent = "Claudey Admin";
  }
}

function formatTokens(n) {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function formatUsd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `$${Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

const IDR_FALLBACK_RATE = 18000;

function formatIdr(usd, rate = IDR_FALLBACK_RATE) {
  if (usd === null || usd === undefined || Number.isNaN(Number(usd))) return "—";
  const idr = Number(usd) * rate;
  if (idr >= 1_000_000) return `Rp ${(idr / 1_000_000).toFixed(1)}M`;
  return `Rp ${Math.round(idr).toLocaleString("en-US")}`;
}

function renderSidebarBudget(dashboard) {
  const widget = byId("sidebarBudget");
  if (!widget || !dashboard) return;
  const spend = Number(dashboard.monthly_spend_usd) || 0;
  const limit = Number(dashboard.monthly_limit_usd) || 0;
  const remaining = Math.max(0, limit - spend);
  const ratio = limit > 0 ? Math.min(spend / limit, 1) : 0;

  widget.hidden = false;

  // Get first day of next month for reset date
  const now = new Date();
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  const options = { month: "short", day: "numeric" };
  const resetDateText = nextMonth.toLocaleDateString("en-US", options);

  byId("sidebarBudgetLeft").textContent = formatUsd(remaining) + " left";
  byId("sidebarBudgetFill").style.width = `${(ratio * 100).toFixed(1)}%`;
  byId("sidebarBudgetReset").textContent = "Resets " + resetDateText;
  const bar = byId("sidebarBudgetBar");
  if (bar) {
    bar.setAttribute("aria-valuenow", String(Math.round(ratio * 100)));
  }
}

function goToUsageView(event) {
  event.preventDefault();
  setActiveView("usage", { scroll: true });
}

const sidebarBudgetStat = byId("sidebarBudgetStat");
const sidebarBudgetUpgrade = byId("sidebarBudgetUpgrade");
if (sidebarBudgetStat) {
  sidebarBudgetStat.addEventListener("click", goToUsageView);
}
if (sidebarBudgetUpgrade) {
  sidebarBudgetUpgrade.addEventListener("click", goToUsageView);
}

api("/admin/api/dashboard")
  .then(renderSidebarBudget)
  .catch(() => {});

function countUp(el, final) {
  if (REDUCED_MOTION) {
    el.textContent = formatTokens(final);
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const t = Math.min((now - start) / 500, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = formatTokens(Math.round(final * eased));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

const USAGE_PERIODS = ["Total", "24h", "7d", "30d"];
const USAGE_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const USAGE_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const USAGE_TREND_SEGMENTS = [
  ["input", "#38bdf8"],
  ["cached_input", "#14b8a6"],
  ["output", "#a78bfa"],
  ["reasoning_output", "#fb7185"],
];
const USAGE_PROVIDER_COLORS = {
  anthropic: "#d97757",
  openai: "#3b82f6",
  nvidia_nim: "#76b900",
  deepseek: "#4d6bfe",
  gemini: "#2196f3",
  ollama: "#404040",
  lmstudio: "#14b8a6",
  llamacpp: "#14b8a6",
  open_router: "#ff9900",
  azure_openai: "#0078d4",
  bedrock: "#ff9900",
  groq: "#f55036",
};

let usagePeriod = "Total";
let usageFullNumbers = false;
let usageTooltipEl = null;

function usageProviderColor(provider, index) {
  return USAGE_PROVIDER_COLORS[provider] || `hsl(${150 + index * 40}, 60%, 45%)`;
}

function usageHeroValue(payload, billing) {
  if (usagePeriod === "Total") {
    // Integrate DeepSeek billing tokens into total
    const native = payload.totals.total_tokens || 0;
    const deepseek = billing?.total_tokens || 0;
    return native + deepseek;
  }
  const windows = payload.windows || {};
  return windows[usagePeriod] || 0;
}

function usageNumberText(n) {
  return usageFullNumbers ? n.toLocaleString("en-US") : formatTokens(n);
}

function formatUsageTimestamp(iso) {
  return iso ? iso.replace("T", " ").replace("+00:00", " UTC") : "never";
}

function getUsageTooltip() {
  if (!usageTooltipEl) {
    usageTooltipEl = document.createElement("div");
    usageTooltipEl.className = "usage-tooltip";
    const date = document.createElement("span");
    date.className = "usage-tooltip-date";
    const value = document.createElement("strong");
    value.className = "usage-tooltip-value";
    usageTooltipEl.append(date, value);
    usageTooltipEl.hidden = true;
    document.body.appendChild(usageTooltipEl);
  }
  return usageTooltipEl;
}

function positionUsageTooltip(event) {
  const tip = getUsageTooltip();
  const pad = 14;
  tip.style.left = `${event.clientX + pad}px`;
  tip.style.top = `${event.clientY + pad}px`;
  const rect = tip.getBoundingClientRect();
  if (rect.right > window.innerWidth) {
    tip.style.left = `${event.clientX - rect.width - pad}px`;
  }
  if (rect.bottom > window.innerHeight) {
    tip.style.top = `${event.clientY - rect.height - pad}px`;
  }
}

function hideUsageTooltip() {
  if (usageTooltipEl) {
    usageTooltipEl.hidden = true;
  }
}

function showUsageTooltip(event, cell) {
  const tip = getUsageTooltip();
  const date = new Date(`${cell.dataset.date}T00:00:00Z`);
  tip.querySelector(".usage-tooltip-date").textContent =
    `${date.toISOString().slice(0, 10)} · ${USAGE_WEEKDAYS[date.getUTCDay()]}`;
  tip.querySelector(".usage-tooltip-value").textContent =
    formatTokens(Number(cell.dataset.value) || 0);
  tip.hidden = false;
  positionUsageTooltip(event);
}

// Heat levels via quantiles over positive day values only; when fewer than
// 4 positive days exist, fall back to ratio-of-max thresholds.
function usageHeatLevels(weeks) {
  const positive = [];
  weeks.forEach((week) => {
    week.days.forEach((value) => {
      if (value > 0) positive.push(value);
    });
  });
  if (positive.length < 4) {
    const max = Math.max(0, ...positive);
    return (value) => {
      if (value <= 0 || max <= 0) return 0;
      const ratio = value / max;
      if (ratio > 0.75) return 4;
      if (ratio > 0.5) return 3;
      if (ratio > 0.25) return 2;
      return 1;
    };
  }
  const sorted = [...positive].sort((a, b) => a - b);
  const pick = (p) => sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * p))];
  const t1 = pick(0.5);
  const t2 = pick(0.75);
  const t3 = pick(0.9);
  return (value) => (value <= 0 ? 0 : value <= t1 ? 1 : value <= t2 ? 2 : value <= t3 ? 3 : 4);
}

function renderUsageHeatmapCard(heatmap) {
  const weeks = (heatmap && heatmap.weeks) || [];
  const card = document.createElement("article");
  card.className = "usage-card";
  const title = document.createElement("h4");
  title.className = "usage-card-title";
  title.textContent = "Activity — last 52 weeks";
  card.appendChild(title);

  const wrap = document.createElement("div");
  wrap.className = "usage-heatmap";

  const months = document.createElement("div");
  months.className = "usage-heatmap-months";
  let previousMonth = -1;
  weeks.forEach((week, weekIndex) => {
    const start = new Date(`${week.start}T00:00:00Z`);
    const month = start.getUTCMonth();
    if (month === previousMonth) return;
    previousMonth = month;
    const label = document.createElement("span");
    label.className = "usage-heatmap-month";
    label.textContent = USAGE_MONTHS[month];
    label.style.gridColumn = `${weekIndex + 1} / span 2`;
    months.appendChild(label);
  });

  const grid = document.createElement("div");
  grid.className = "usage-heatmap-grid";
  grid.setAttribute("role", "img");
  grid.setAttribute("aria-label", "Token usage heatmap over the last 52 weeks");

  // Attach mouseleave to the entire grid to handle fast mouse movements
  grid.addEventListener("mouseleave", (e) => {
    if (!e.relatedTarget || !grid.contains(e.relatedTarget)) {
      hideUsageTooltip();
    }
  });

  const levelFor = usageHeatLevels(weeks);
  weeks.forEach((week) => {
    const weekStart = new Date(`${week.start}T00:00:00Z`);
    week.days.forEach((value, index) => {
      const cell = document.createElement("span");
      const date = new Date(weekStart);
      date.setUTCDate(date.getUTCDate() + index);
      cell.className = `heat-cell heat-${levelFor(value)}`;
      cell.dataset.date = date.toISOString().slice(0, 10);
      cell.dataset.value = String(value);
      cell.addEventListener("mouseenter", (event) => showUsageTooltip(event, cell));
      cell.addEventListener("mousemove", positionUsageTooltip);
      cell.addEventListener("mouseleave", hideUsageTooltip);
      grid.appendChild(cell);
    });
  });

  wrap.append(months, grid);
  card.appendChild(wrap);
  // Anchor the heatmap on the current (rightmost) week so the most recent
  // activity is visible immediately; scroll left to reach older weeks.
  requestAnimationFrame(() => {
    wrap.scrollLeft = wrap.scrollWidth;
  });
  return card;
}

const TREND_FRACTIONS = [0, 1 / 3, 2 / 3, 1];

function trendShortDate(iso) {
  const date = new Date(`${iso}T00:00:00Z`);
  return `${USAGE_MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}`;
}

function trendTooltipLines(row) {
  const lines = [`${row.date} · ${formatTokens(row.total_tokens || 0)} total`];
  USAGE_TREND_SEGMENTS.forEach(([key]) => {
    const value = row[key] || 0;
    if (value > 0) lines.push(`${key}: ${formatTokens(value)}`);
  });
  return lines.join("\n");
}

function buildTrendAreaChart(rows) {
  // Firecrawl-style single-line area chart built as an inline SVG.
  const SVG_NS = "http://www.w3.org/2000/svg";
  const W = 600;
  const H = 180;
  const PAD_LEFT = 48;
  const PAD_RIGHT = 10;
  const PAD_TOP = 10;
  const PAD_BOTTOM = 22;
  const PLOT_W = W - PAD_LEFT - PAD_RIGHT;
  const PLOT_H = H - PAD_TOP - PAD_BOTTOM;

  const maxTotal = Math.max(1, ...rows.map((row) => row.total_tokens || 0));
  const xFor = (index) =>
    PAD_LEFT + (rows.length === 1 ? PLOT_W / 2 : (index / (rows.length - 1)) * PLOT_W);
  const yFor = (value) => PAD_TOP + PLOT_H - (value / maxTotal) * PLOT_H;
  const plotBottom = PAD_TOP + PLOT_H;

  const points = rows.map((row, index) => ({
    x: xFor(index),
    y: yFor(row.total_tokens || 0),
    row,
  }));

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(" ");
  const areaPath =
    `${linePath} L${(PAD_LEFT + PLOT_W).toFixed(1)},${plotBottom} L${PAD_LEFT},${plotBottom} Z`;

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "usage-trend-svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Daily token usage over the last 30 days");

  const defs = document.createElementNS(SVG_NS, "defs");
  const gradient = document.createElementNS(SVG_NS, "linearGradient");
  gradient.id = "trendAreaFill";
  gradient.setAttribute("x1", "0");
  gradient.setAttribute("y1", "0");
  gradient.setAttribute("x2", "0");
  gradient.setAttribute("y2", "1");
  const stops = [
    { offset: "0%", opacity: "0.28" },
    { offset: "100%", opacity: "0" },
  ];
  stops.forEach((stop) => {
    const el = document.createElementNS(SVG_NS, "stop");
    el.setAttribute("offset", stop.offset);
    el.setAttribute("stop-color", "#ff4d00");
    el.setAttribute("stop-opacity", stop.opacity);
    gradient.appendChild(el);
  });
  defs.appendChild(gradient);
  svg.appendChild(defs);

  // Horizontal gridlines with left token labels.
  TREND_FRACTIONS.forEach((fraction) => {
    const y = PAD_TOP + PLOT_H * (1 - fraction);
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("class", "usage-trend-grid");
    line.setAttribute("x1", String(PAD_LEFT));
    line.setAttribute("x2", String(PAD_LEFT + PLOT_W));
    line.setAttribute("y1", y.toFixed(1));
    line.setAttribute("y2", y.toFixed(1));
    svg.appendChild(line);
    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("class", "usage-trend-axis");
    label.setAttribute("x", String(PAD_LEFT - 6));
    label.setAttribute("y", (y + 3).toFixed(1));
    label.textContent = fraction === 0 ? "0" : formatTokens(Math.round(maxTotal * fraction));
    svg.appendChild(label);
  });

  // X-axis date labels on a few evenly spaced days plus the latest.
  const labelIndices = [];
  rows.forEach((_, index) => {
    if (index % Math.max(1, Math.floor(rows.length / 6)) === 0) labelIndices.push(index);
  });
  labelIndices.push(rows.length - 1);
  [...new Set(labelIndices)].forEach((index) => {
    const point = points[index];
    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("class", "usage-trend-axis");
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("x", point.x.toFixed(1));
    label.setAttribute("y", String(H - 6));
    label.textContent = trendShortDate(point.row.date);
    svg.appendChild(label);
  });

  const area = document.createElementNS(SVG_NS, "path");
  area.setAttribute("class", "usage-trend-area");
  area.setAttribute("d", areaPath);
  svg.appendChild(area);

  const line = document.createElementNS(SVG_NS, "path");
  line.setAttribute("class", "usage-trend-line");
  line.setAttribute("d", linePath);
  svg.appendChild(line);

  // One point per day, each exposing a per-segment tooltip.
  points.forEach((point) => {
    const dot = document.createElementNS(SVG_NS, "circle");
    dot.setAttribute("class", "usage-trend-dot");
    dot.setAttribute("cx", point.x.toFixed(1));
    dot.setAttribute("cy", point.y.toFixed(1));
    dot.setAttribute("r", "2.5");
    const tip = document.createElementNS(SVG_NS, "title");
    tip.textContent = trendTooltipLines(point.row);
    dot.appendChild(tip);
    svg.appendChild(dot);
  });

  return svg;
}

function renderUsageTrendCard(daily) {
  const rows = daily || [];
  const card = document.createElement("article");
  card.className = "usage-card";

  const head = document.createElement("div");
  head.className = "usage-trend-head";
  const title = document.createElement("h4");
  title.className = "usage-card-title";
  title.textContent = "Last 30 days";
  const headTotal = document.createElement("span");
  headTotal.className = "usage-trend-total";
  headTotal.textContent = formatTokens(rows.reduce((sum, row) => sum + (row.total_tokens || 0), 0));
  head.append(title, headTotal);
  card.appendChild(head);

  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "usage-empty-note";
    note.textContent = "No data yet.";
    card.appendChild(note);
    return card;
  }

  card.appendChild(buildTrendAreaChart(rows));
  return card;
}

function renderUsageProvidersStats(providers, limit = 4) {
  if (!providers || !providers.length) {
    const grid = document.createElement("div");
    grid.className = "usage-stat-grid";
    const empty = document.createElement("p");
    empty.className = "usage-empty-note";
    empty.textContent = "No provider data yet.";
    grid.appendChild(empty);
    return grid;
  }
  const sorted = [...providers].sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0)).slice(0, limit);
  const grid = document.createElement("div");
  grid.className = "usage-provider-stats-grid";
  sorted.forEach((provider, index) => {
    const cell = document.createElement("div");
    cell.className = "usage-provider-stat-cell";
    const color = usageProviderColor(provider.provider, index);
    const dot = document.createElement("span");
    dot.className = "usage-provider-stat-dot";
    dot.style.background = color;
    const name = document.createElement("span");
    name.className = "usage-provider-stat-name";
    name.textContent = provider.provider;
    const tokens = document.createElement("span");
    tokens.className = "usage-provider-stat-tokens";
    const final = provider.total_tokens || 0;
    tokens.dataset.final = final;
    tokens.textContent = formatTokens(final);
    cell.append(dot, name, tokens);
    grid.appendChild(cell);
    // Tween on mount
    requestAnimationFrame(() => {
      tokens.textContent = formatTokens(Number(tokens.dataset.final));
    });
  });
  return grid;
}

function renderUsageBillingRow(label, value, accent) {
  const row = document.createElement("div");
  row.className = "usage-billing-row";
  const labelEl = document.createElement("span");
  labelEl.className = "usage-billing-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.className = accent ? "usage-billing-value accent" : "usage-billing-value";
  valueEl.textContent = value;
  row.append(labelEl, valueEl);
  return row;
}

function renderUsageBillingCard(billing) {
  if (!billing || (!billing.available && !billing.configured)) return null;
  const card = document.createElement("article");
  card.className = "usage-card usage-billing";
  const title = document.createElement("h4");
  title.className = "usage-card-title";
  title.textContent = "DeepSeek billing";
  const status = document.createElement("span");
  status.className = "status-pill";
  card.append(title, status);

  if (!billing.available) {
    status.className = "status-pill warn";
    status.textContent = "Syncing";
    const hint = document.createElement("p");
    hint.className = "usage-billing-hint";
    hint.textContent = "Syncing on next load…";
    card.appendChild(hint);
    return card;
  }

  const syncStatus = billing.status || "ok";
  if (syncStatus === "invalid_token") {
    status.className = "status-pill warn";
    status.textContent = "Session expired";
    const hint = document.createElement("p");
    hint.className = "usage-billing-hint";
    hint.textContent = "Paste a fresh userToken from platform.deepseek.com.";
    card.appendChild(hint);
  } else if (syncStatus === "offline") {
    status.className = "status-pill warn";
    status.textContent = "Offline";
  } else if (syncStatus === "not_configured") {
    status.className = "status-pill warn";
    status.textContent = "Not configured";
  } else {
    status.className = "status-pill ok";
    status.textContent = "Synced";
  }

  const rows = document.createElement("div");
  rows.className = "usage-billing-rows";
  rows.append(
    renderUsageBillingRow("Balance", formatUsd(billing.balance_usd), true),
    renderUsageBillingRow("All-time cost", formatUsd(billing.total_cost_usd), true),
    renderUsageBillingRow("Tokens", formatTokens(billing.total_tokens || 0), false),
    renderUsageBillingRow(
      "Requests",
      (billing.total_requests || 0).toLocaleString("en-US"),
      false,
    ),
    renderUsageBillingRow("Last synced", formatUsageTimestamp(billing.last_synced), false),
  );
  card.appendChild(rows);
  return card;
}

function renderUsageEmpty(kind) {
  const card = document.createElement("div");
  card.className = "usage-empty";
  const title = document.createElement("h3");
  const body = document.createElement("p");
  if (kind === "not-found") {
    title.textContent = "No usage recorded yet";
    body.textContent = "claudey writes ~/.claudey/usage.jsonl as requests complete.";
  } else if (kind === "empty") {
    title.textContent = "No requests served yet";
    body.textContent = "Usage appears after your next conversation.";
  } else {
    title.textContent = "Could not load usage data";
    body.textContent = "The usage endpoint is unreachable. Try refreshing.";
  }
  card.append(title, body);
  return card;
}

function renderUsageHero(payload, billing) {
  const card = document.createElement("article");
  card.className = "usage-card usage-hero";

  // MagicUI-style concentric ripple rings behind the total number.
  const ripple = document.createElement("div");
  ripple.className = "usage-hero-ripple";
  ripple.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 8; i += 1) {
    const circle = document.createElement("div");
    circle.className = "usage-hero-ripple-circle";
    const size = 140 + i * 70;
    circle.style.width = `${size}px`;
    circle.style.height = `${size}px`;
    circle.style.opacity = String(Math.max(0.08, 0.4 - i * 0.045));
    circle.style.animationDelay = `${i * 0.06}s`;
    ripple.appendChild(circle);
  }
  card.appendChild(ripple);

  const tabs = document.createElement("div");
  tabs.className = "usage-period-tabs";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Period");

  const indicator = document.createElement("div");
  indicator.className = "usage-period-pill-indicator";
  indicator.setAttribute("aria-hidden", "true");
  tabs.appendChild(indicator);

  const positionIndicator = (active) => {
    indicator.style.left = `${active.offsetLeft}px`;
    indicator.style.width = `${active.offsetWidth}px`;
  };

  USAGE_PERIODS.forEach((period, index) => {
    if (index > 0) {
      const sep = document.createElement("div");
      sep.className = "usage-period-sep";
      sep.setAttribute("aria-hidden", "true");
      tabs.appendChild(sep);
    }
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = `usage-period-tab${period === usagePeriod ? " active" : ""}`;
    tab.textContent = period;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(period === usagePeriod));
    tab.addEventListener("click", () => {
      if (period === usagePeriod) return;
      usagePeriod = period;
      tabs.querySelectorAll(".usage-period-tab").forEach((other) => {
        other.classList.toggle("active", other === tab);
        other.setAttribute("aria-selected", String(other === tab));
      });
      positionIndicator(tab);
      // Tween animation for all tabs
      tabs.querySelectorAll(".usage-period-tab").forEach((t) => {
        t.style.transform = "scale(0.95)";
        setTimeout(() => { t.style.transform = ""; }, 100);
      });
      if (usageFullNumbers) {
        heroNumber.textContent = usageNumberText(usageHeroValue(payload, billing));
      } else {
        countUp(heroNumber, usageHeroValue(payload, billing));
      }
    });
    tabs.appendChild(tab);
  });
  card.appendChild(tabs);
  // Anchor the sliding highlight on the active period after layout.
  requestAnimationFrame(() => {
    const active = tabs.querySelector(".usage-period-tab.active");
    if (active) positionIndicator(active);
  });

  const heroNumber = document.createElement("button");
  heroNumber.type = "button";
  heroNumber.className = "usage-hero-number";
  heroNumber.title = "Click to toggle between compact and full numbers";
  heroNumber.setAttribute("aria-pressed", String(usageFullNumbers));
  heroNumber.addEventListener("click", () => {
    usageFullNumbers = !usageFullNumbers;
    heroNumber.setAttribute("aria-pressed", String(usageFullNumbers));
    heroNumber.textContent = usageNumberText(usageHeroValue(payload, billing));
  });
  countUp(heroNumber, usageHeroValue(payload, billing));
  card.appendChild(heroNumber);

  const costRow = document.createElement("div");
  costRow.className = "usage-hero-costs";
  const usdCost = billing?.total_cost_usd !== undefined ? formatUsd(billing.total_cost_usd) : "—";
  const idrCost = billing?.total_cost_usd !== undefined ? formatIdr(billing.total_cost_usd) : "—";
  const usdEl = document.createElement("span");
  usdEl.className = "usage-hero-cost-item";
  usdEl.innerHTML = `<strong>Total cost:</strong> ${usdCost}`;
  const idrEl = document.createElement("span");
  idrEl.className = "usage-hero-cost-item";
  idrEl.innerHTML = `<strong>IDR:</strong> ${idrCost}`;
  costRow.append(usdEl, idrEl);
  card.appendChild(costRow);

  return card;
}

function renderUsageProviders(payload) {
  const providers = payload.providers || [];
  const card = document.createElement("article");
  card.className = "usage-card";
  const title = document.createElement("h4");
  title.className = "usage-card-title";
  title.textContent = "Providers";
  card.appendChild(title);

  if (!providers.length) {
    const note = document.createElement("p");
    note.className = "usage-empty-note";
    note.textContent = "No provider data yet.";
    card.appendChild(note);
    return card;
  }

  const total = providers.reduce((sum, provider) => sum + (provider.total_tokens || 0), 0);

  const bar = document.createElement("div");
  bar.className = "usage-provider-bar";
  bar.setAttribute("role", "img");
  bar.setAttribute("aria-label", "Token share by provider");
  providers.forEach((provider, index) => {
    if ((provider.total_tokens || 0) <= 0 || total <= 0) return;
    const segment = document.createElement("div");
    segment.className = "usage-provider-bar-seg";
    segment.style.background = usageProviderColor(provider.provider, index);
    segment.style.width = `${(provider.total_tokens / total) * 100}%`;
    segment.title = `${provider.provider} · ${formatTokens(provider.total_tokens)} tokens`;
    bar.appendChild(segment);
  });
  card.appendChild(bar);

  const grid = document.createElement("div");
  grid.className = "usage-provider-grid";
  providers.forEach((provider, index) => {
    const share = total > 0 ? (provider.total_tokens / total) * 100 : 0;
    const color = usageProviderColor(provider.provider, index);
    const item = document.createElement("button");
    item.type = "button";
    item.className = "usage-provider-card";
    item.setAttribute("aria-expanded", "false");
    const head = document.createElement("div");
    head.className = "usage-provider-head";
    const name = document.createElement("span");
    name.className = "usage-provider-name";
    name.textContent = provider.provider;
    const meta = document.createElement("span");
    meta.className = "usage-provider-stats";
    meta.textContent = `${share.toFixed(2)}% · ${provider.model_count || 0} models`;
    head.append(name, meta);
    const tokens = document.createElement("span");
    tokens.className = "usage-provider-tokens";
    tokens.textContent = formatTokens(provider.total_tokens || 0);
    const modelsWrap = document.createElement("div");
    modelsWrap.className = "usage-provider-models";
    modelsWrap.hidden = true;
    (payload.models || [])
      .filter((model) => model.provider_id === provider.provider)
      .sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0))
      .forEach((model) => {
        const modelShare = total > 0 ? ((model.total_tokens || 0) / total) * 100 : 0;
        const row = document.createElement("div");
        row.className = "usage-model-row";
        const modelName = document.createElement("span");
        modelName.className = "usage-model-name";
        modelName.textContent = model.model;
        modelName.title = model.model;
        const modelTokens = document.createElement("span");
        modelTokens.className = "usage-model-tokens";
        modelTokens.textContent = formatTokens(model.total_tokens || 0);
        const shareEl = document.createElement("span");
        shareEl.className = "usage-model-share";
        shareEl.textContent = `${modelShare.toFixed(2)}%`;
        const modelBar = document.createElement("div");
        modelBar.className = "usage-model-bar";
        modelBar.style.background = color;
        modelBar.style.width = `${Math.min(modelShare, 100)}%`;
        row.append(modelName, modelTokens, shareEl, modelBar);
        modelsWrap.appendChild(row);
      });
    item.append(head, tokens, modelsWrap);
    item.addEventListener("click", () => {
      modelsWrap.hidden = !modelsWrap.hidden;
      item.setAttribute("aria-expanded", String(!modelsWrap.hidden));
    });
    grid.appendChild(item);
  });
  card.appendChild(grid);
  return card;
}

function renderUsageDailyTable(daily, billing) {
  const rows = daily || [];
  const costByDate = new Map();
  (billing && billing.days || []).forEach((day) => {
    costByDate.set(day.date, day.cost_usd);
  });
  const card = document.createElement("article");
  card.className = "usage-card";
  const title = document.createElement("h4");
  title.className = "usage-card-title";
  title.textContent = "Daily breakdown";
  card.appendChild(title);

  const scroll = document.createElement("div");
  scroll.className = "usage-table-scroll";
  const table = document.createElement("table");
  table.className = "usage-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Date", "Total", "Input", "Output", "Cached", "Reasoning", "Conversations", "Cost"].forEach((label) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");

  const totals = rows.reduce(
    (acc, row) => ({
      total_tokens: acc.total_tokens + (row.total_tokens || 0),
      input_tokens: acc.input_tokens + (row.input_tokens || 0),
      output_tokens: acc.output_tokens + (row.output_tokens || 0),
      cached_input_tokens: acc.cached_input_tokens + (row.cached_input_tokens || 0),
      reasoning_output_tokens: acc.reasoning_output_tokens + (row.reasoning_output_tokens || 0),
      conversations: acc.conversations + (row.conversations || 0),
      cost_usd: acc.cost_usd + (costByDate.get(row.date) || 0),
    }),
    {
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      cached_input_tokens: 0,
      reasoning_output_tokens: 0,
      conversations: 0,
      cost_usd: 0,
    }
  );
  const totalRow = document.createElement("tr");
  totalRow.className = "usage-table-total";
  [
    "Total",
    formatTokens(totals.total_tokens),
    formatTokens(totals.input_tokens),
    formatTokens(totals.output_tokens),
    formatTokens(totals.cached_input_tokens),
    formatTokens(totals.reasoning_output_tokens),
    String(totals.conversations),
    formatUsd(totals.cost_usd),
  ].forEach((text) => {
    const td = document.createElement("td");
    td.textContent = text;
    totalRow.appendChild(td);
  });
  tbody.appendChild(totalRow);

  [...rows].reverse().forEach((row) => {
    const tr = document.createElement("tr");
    if (!(row.total_tokens || 0)) tr.className = "zero";
    const cost = costByDate.has(row.date) ? formatUsd(costByDate.get(row.date)) : "—";
    [
      row.date,
      formatTokens(row.total_tokens || 0),
      formatTokens(row.input_tokens || 0),
      formatTokens(row.output_tokens || 0),
      formatTokens(row.cached_input_tokens || 0),
      formatTokens(row.reasoning_output_tokens || 0),
      String(row.conversations || 0),
      cost,
    ].forEach((text) => {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.append(thead, tbody);
  scroll.appendChild(table);
  card.appendChild(scroll);
  return card;
}

function renderUsage(payload) {
  const container = byId("usageSections");
  container.innerHTML = "";

  const strip = document.createElement("section");
  strip.className = "provider-strip";

  const header = document.createElement("div");
  header.className = "strip-header";
  const heading = document.createElement("div");
  const h3 = document.createElement("h3");
  h3.textContent = "Token usage";
  const sub = document.createElement("p");
  heading.append(h3, sub);

  const pill = document.createElement("span");
  pill.className = "status-pill";
  const refresh = document.createElement("button");
  refresh.type = "button";
  refresh.className = "secondary-button";
  refresh.textContent = "Refresh";
  refresh.addEventListener("click", () => {
    state.usageLoaded = false;
    loadUsage();
  });
  const actions = document.createElement("div");
  actions.className = "usage-actions";
  actions.append(pill, refresh);
  header.append(heading, actions);
  strip.appendChild(header);

  if (!payload.available) {
    pill.className = "status-pill warn";
    pill.textContent = "Not found";
    sub.textContent = "Claudey records its own usage as requests complete.";
    strip.appendChild(renderUsageEmpty("not-found"));
    container.appendChild(strip);
    return;
  }

  if (payload.total_entries === 0) {
    pill.className = "status-pill warn";
    pill.textContent = "Collecting";
    sub.textContent = "No usage recorded yet — claudey writes it as requests complete.";
    strip.appendChild(renderUsageEmpty("empty"));
    container.appendChild(strip);
    return;
  }

  pill.className = "status-pill ok";
  pill.textContent = "Tracking";
  sub.textContent = `Collected from ~/.claudey/usage.jsonl · last updated ${formatUsageTimestamp(payload.last_updated)}`;

  const grid = document.createElement("div");
  grid.className = "usage-grid";
  const left = document.createElement("div");
  left.className = "usage-col";
  const right = document.createElement("div");
  right.className = "usage-col";
  // Use top providers in left column instead of stat cells
  left.append(
    renderUsageProvidersStats(payload.providers),
    renderUsageHeatmapCard(payload.heatmap),
    renderUsageTrendCard(payload.daily),
  );
  right.append(renderUsageHero(payload, payload.billing));
  const billingCard = renderUsageBillingCard(payload.billing);
  if (billingCard) right.appendChild(billingCard);
  right.append(
    renderUsageProviders(payload),
    renderUsageDailyTable(payload.daily, payload.billing),
  );
  grid.append(left, right);
  strip.appendChild(grid);
  container.appendChild(strip);
}

async function loadUsage() {
  const container = byId("usageSections");
  if (!container) return;
  if (state.usageLoaded && container.hasChildNodes()) return;
  try {
    const payload = await api("/admin/api/usage");
    state.usageLoaded = true;
    renderUsage(payload);
  } catch {
    state.usageLoaded = true;
    container.innerHTML = "";
    const strip = document.createElement("section");
    strip.className = "provider-strip";
    strip.appendChild(renderUsageEmpty("error"));
    container.appendChild(strip);
  }
}

document.addEventListener("keydown", (event) => {
  if (event.defaultPrevented || event.isComposing) return;
  const modifier = event.metaKey || event.ctrlKey;
  if (!modifier) return;
  const key = event.key.toLowerCase();
  if (key === "enter") {
    const applyButton = byId("applyButton");
    if (applyButton.disabled) return;
    event.preventDefault();
    apply();
  } else if (key === "s") {
    event.preventDefault();
    validate(true);
  }
});

byId("validateButton").addEventListener("click", () => validate(true));
byId("applyButton").addEventListener("click", apply);
byId("restartButton").addEventListener("click", restartServer);

const sidebarToggle = byId("sidebarToggle");
const sectionNav = byId("sectionNav");
const mobileQuery = window.matchMedia("(max-width: 900px)");

function applySidebarCollapsed(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  const pinLabel = collapsed ? "Pin sidebar open" : "Unpin sidebar";
  sidebarToggle.setAttribute("aria-label", pinLabel);
  sidebarToggle.title = pinLabel;
  sectionNav.inert = collapsed && mobileQuery.matches;
  localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? "collapsed" : "expanded");
}

sidebarToggle.addEventListener("click", () => {
  if (window.__sidebarTweenToggle) {
    window.__sidebarTweenToggle();
    return;
  }
  applySidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
});

const sidebarCollapseBtn = byId("sidebarCollapseBtn");
if (sidebarCollapseBtn) {
  sidebarCollapseBtn.addEventListener("click", (event) => {
    event.preventDefault();
    if (window.__sidebarTweenToggle) {
      window.__sidebarTweenToggle();
      return;
    }
    applySidebarCollapsed(true);
  });
}

mobileQuery.addEventListener("change", (event) => {
  sectionNav.inert = event.matches && document.body.classList.contains("sidebar-collapsed");
});

applySidebarCollapsed(localStorage.getItem(SIDEBAR_STATE_KEY) === "collapsed");

document.addEventListener("pointerdown", (event) => {

  state.modelComboboxes.forEach((combobox) => {
    if (combobox.isOpen && !combobox.element.contains(event.target)) combobox.close();
  });
});

// Custom provider dialogs
function showCustomProviderDialog(providerType) {
  const dialog = document.createElement("dialog");
  dialog.className = "custom-provider-dialog";
  dialog.innerHTML = `
    <form method="dialog">
      <h3>Add ${providerType === 'openai' ? 'OpenAI-compatible' : 'Anthropic-compatible'} Provider</h3>
      <div class="field">
        <label for="providerName">Provider Name</label>
        <input type="text" id="providerName" placeholder="e.g. My Custom Provider" required />
      </div>
      <div class="field">
        <label for="baseUrl">Base URL</label>
        <input type="url" id="baseUrl" placeholder="https://api.example.com/v1" required />
      </div>
      <div class="field">
        <label for="apiKey">API Key</label>
        <input type="password" id="apiKey" placeholder="sk-xxxxx" />
      </div>
      <div class="field">
        <label for="modelId">Model ID (optional)</label>
        <input type="text" id="modelId" placeholder="e.g. gpt-4o-mini" />
        <p class="field-hint">If the provider has no /models endpoint, add a model ID to validate via a chat request.</p>
      </div>
      <div class="check-row">
        <button type="button" id="checkProviderBtn" class="secondary-button">Check</button>
        <div id="checkResult" class="custom-provider-check-result" hidden></div>
      </div>
      <div class="dialog-actions">
        <button type="button" class="secondary-button" onclick="this.closest('dialog').close()">Cancel</button>
        <button type="button" id="addProviderBtn" class="primary-button">Add Provider</button>
      </div>
    </form>
  `;

  let checkPassed = false;

  const resetCheck = () => {
    checkPassed = false;
    const result = dialog.querySelector("#checkResult");
    result.hidden = true;
    result.textContent = "";
    result.className = "custom-provider-check-result";
  };
  ["#providerName", "#baseUrl", "#apiKey", "#modelId"].forEach((selector) => {
    dialog.querySelector(selector).addEventListener("input", resetCheck);
  });

  const checkBtn = dialog.querySelector("#checkProviderBtn");
  checkBtn.addEventListener("click", async () => {
    const baseUrl = dialog.querySelector("#baseUrl").value.trim();
    const apiKey = dialog.querySelector("#apiKey").value;
    const modelId = dialog.querySelector("#modelId").value.trim();
    const result = dialog.querySelector("#checkResult");

    result.hidden = true;
    result.className = "custom-provider-check-result";
    checkBtn.disabled = true;
    try {
      const response = await fetch("/admin/api/providers/custom/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: baseUrl,
          api_key: apiKey,
          type: providerType,
          model_id: modelId || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Check failed");

      result.hidden = false;
      if (data.valid) {
        checkPassed = true;
        result.textContent = `Valid — ${data.method === "chat" ? "chat request OK" : "models endpoint OK"}`;
        result.classList.add("valid");
      } else {
        result.textContent = `Invalid — ${data.error || "could not connect"}`;
        result.classList.add("invalid");
      }
    } catch (error) {
      result.hidden = false;
      result.textContent = `Invalid — ${error.message}`;
      result.classList.add("invalid");
    } finally {
      checkBtn.disabled = false;
    }
  });

  dialog.querySelector("#addProviderBtn").addEventListener("click", async () => {
    if (!checkPassed) {
      showMessage("Run Check first to verify the provider connection", "error");
      return;
    }
    const name = dialog.querySelector("#providerName").value;
    const baseUrl = dialog.querySelector("#baseUrl").value;
    const apiKey = dialog.querySelector("#apiKey").value;

    try {
      const response = await fetch("/admin/api/providers/custom", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          type: providerType,
          name: name,
          base_url: baseUrl,
          api_key: apiKey,
        }),
      });

      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Failed to create provider");

      showMessage(result.message || `Provider ${name} added successfully`, "success");
      dialog.close();
      await load();
    } catch (error) {
      showMessage(`Failed to create provider: ${error.message}`, "error");
    }
  });

  document.body.appendChild(dialog);
  dialog.showModal();
}

async function removeCustomProvider(provider) {
  if (!window.confirm(`Delete custom provider "${provider.display_name}"?`)) return;
  try {
    const response = await api(`/admin/api/providers/custom/${provider.provider_id}`, {
      method: "DELETE",
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Failed to delete provider");
    showMessage(result.message || "Custom provider deleted", "success");
    await load();
  } catch (error) {
    showMessage(`Failed to delete provider: ${error.message}`, "error");
  }
}

// Combo (fallback-chain) management
async function renderCombos() {
  const grid = byId("comboGrid");
  if (!grid) return;
  let combos = [];
  try {
    const data = await api("/admin/api/combos");
    combos = data.combos || [];
  } catch (error) {
    grid.innerHTML = "";
    const msg = document.createElement("p");
    msg.className = "combo-empty";
    msg.textContent = `Could not load fallback combos: ${error.message}`;
    grid.appendChild(msg);
    return;
  }
  grid.innerHTML = "";
  byId("comboStrip").hidden = false;
  if (combos.length === 0) {
    const empty = document.createElement("p");
    empty.className = "combo-empty";
    empty.textContent =
      "No fallback combos yet. Add one to reference it from tier settings with @combo:id.";
    grid.appendChild(empty);
    return;
  }
  combos.forEach((combo) => {
    const card = document.createElement("article");
    card.className = "provider-card combo-card";
    card.dataset.combo = combo.combo_id;

    const title = document.createElement("div");
    title.className = "provider-title";
    const name = document.createElement("strong");
    name.textContent = combo.display_name;
    const badge = document.createElement("span");
    badge.className = "custom-compatible-badge";
    badge.textContent = combo.enabled ? "Enabled" : "Disabled";
    name.after(badge);
    title.appendChild(name);

    const meta = document.createElement("div");
    meta.className = "combo-nodes";
    const nodeCount = `${(combo.nodes || []).length} node${combo.nodes.length === 1 ? "" : "s"}`;
    meta.textContent = `${nodeCount} · ${combo.nodes.map((n) => n.provider_model_ref).join(" → ")}`;
    meta.setAttribute(
      "title",
      (combo.nodes || [])
        .map(
          (n) =>
            `${n.enabled ? "" : "(disabled) "}${n.provider_model_ref}` +
            (n.priority ? ` [p${n.priority}]` : ""),
        )
        .join(", "),
    );
    title.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "provider-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary-button";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => showComboDialog(combo));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => removeCombo(combo));
    actions.append(edit, remove);

    card.append(title, actions);
    card.style.setProperty("--card-index", grid.children.length);
    grid.appendChild(card);
  });
}

function comboNodeRows(combo) {
  const nodes = (combo && combo.nodes) || [];
  if (nodes.length > 0) return nodes;
  return [{ provider_model_ref: "", enabled: true, priority: 0 }];
}

let comboNodeRefKey = 0;

function addComboNodeRow(rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "combo-node-row";

  // Node refs are provider/model pairs, so reuse the model combobox to offer
  // discovered-model recommendations while still allowing custom slugs.
  const refInput = document.createElement("input");
  refInput.type = "text";
  refInput.className = "combo-node-ref";
  refInput.placeholder = "provider/model";
  refInput.setAttribute("aria-label", "Provider model reference");
  const refCombobox = new ModelCombobox(refInput, {
    type: "model",
    key: `combo-node-ref-${++comboNodeRefKey}`,
    label: "Provider model reference",
  });

  const toggleLabel = document.createElement("label");
  toggleLabel.className = "combo-node-toggle";
  const enabledCheckbox = document.createElement("input");
  enabledCheckbox.type = "checkbox";
  enabledCheckbox.className = "combo-node-enabled";
  enabledCheckbox.checked = true;
  toggleLabel.append(enabledCheckbox, document.createTextNode(" enabled"));

  const priorityInput = document.createElement("input");
  priorityInput.type = "number";
  priorityInput.className = "combo-node-priority";
  priorityInput.value = "0";
  priorityInput.min = "0";
  priorityInput.setAttribute("aria-label", "Priority");

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "combo-node-remove secondary-button";
  removeButton.setAttribute("aria-label", "Remove node");
  removeButton.textContent = "×";
  removeButton.addEventListener("click", () => {
    wrapper.remove();
    state.modelComboboxes.delete(refCombobox);
  });

  wrapper.append(refCombobox.element, toggleLabel, priorityInput, removeButton);
  rows.appendChild(wrapper);
  return refCombobox;
}

function showComboDialog(combo) {
  const dialog = document.createElement("dialog");
  dialog.className = "custom-provider-dialog combo-dialog";
  const isEdit = Boolean(combo && combo.combo_id);
  dialog.innerHTML = `
    <form method="dialog">
      <h3>${isEdit ? "Edit" : "Add"} Fallback Combo</h3>
      <div class="field">
        <label for="comboName">Combo Name</label>
        <input type="text" id="comboName" placeholder="e.g. Flagship" value="${isEdit ? escapeHtml(combo.display_name) : ""}" required />
      </div>
      <div class="field">
        <label for="comboNodes">Fallback chain (tried in order, lowest priority first)</label>
        <div id="comboNodeRows" class="combo-node-rows"></div>
        <button type="button" id="addComboNodeBtn" class="secondary-button">Add node</button>
      </div>
      <label class="combo-node-toggle combo-enabled-toggle">
        <input type="checkbox" id="comboEnabled" ${!isEdit || combo.enabled ? "checked" : ""} />
        combo enabled
      </label>
      <div class="dialog-actions">
        <button type="button" class="secondary-button" id="comboValidateBtn">Validate nodes</button>
        <div id="comboValidateResult" class="custom-provider-check-result" hidden></div>
        <button type="button" class="secondary-button" onclick="this.closest('dialog').close()">Cancel</button>
        <button type="button" id="comboSaveBtn" class="primary-button">${isEdit ? "Save Changes" : "Add Combo"}</button>
      </div>
    </form>
  `;

  const rows = dialog.querySelector("#comboNodeRows");
  const dialogComboboxes = [];
  comboNodeRows(combo).forEach((node) => {
    dialogComboboxes.push(addComboNodeRow(rows));
    const row = rows.lastElementChild;
    row.querySelector(".combo-node-ref").value = node.provider_model_ref;
    row.querySelector(".combo-node-enabled").checked = node.enabled;
    row.querySelector(".combo-node-priority").value = node.priority;
  });
  // Drop the row comboboxes and the dialog element once it closes so they
  // don't accumulate across opens.
  dialog.addEventListener("close", () => {
    dialogComboboxes.forEach((combobox) => state.modelComboboxes.delete(combobox));
    dialog.remove();
  });
  dialog.querySelector("#addComboNodeBtn").addEventListener("click", () => {
    addComboNodeRow(rows);
  });

  const collectNodes = () =>
    Array.from(rows.querySelectorAll(".combo-node-row"))
      .map((row) => ({
        provider_model_ref: row.querySelector(".combo-node-ref").value.trim(),
        enabled: row.querySelector(".combo-node-enabled").checked,
        priority: Number(row.querySelector(".combo-node-priority").value) || 0,
      }))
      .filter((node) => node.provider_model_ref.length > 0);

  const validateResult = dialog.querySelector("#comboValidateResult");
  const showValidation = (text, className) => {
    validateResult.hidden = false;
    validateResult.textContent = text;
    validateResult.className = `custom-provider-check-result ${className}`;
  };

  dialog
    .querySelector("#comboValidateBtn")
    .addEventListener("click", async () => {
      const name = dialog.querySelector("#comboName").value.trim();
      const nodes = collectNodes();
      validateResult.hidden = true;
      try {
        const data = await api("/admin/api/combos/validate", {
          method: "POST",
          body: JSON.stringify({ display_name: name, nodes, enabled: true }),
        });
        if (data.valid) {
          showValidation("Valid — nodes are well-formed provider/model refs", "valid");
        } else {
          showValidation(`Invalid — ${data.error || "bad node reference"}`, "invalid");
        }
      } catch (error) {
        showValidation(`Invalid — ${error.message}`, "invalid");
      }
    });

  dialog.querySelector("#comboSaveBtn").addEventListener("click", async () => {
    const name = dialog.querySelector("#comboName").value.trim();
    const nodes = collectNodes();
    if (!name) {
      showMessage("A combo name is required", "error");
      return;
    }
    if (nodes.length === 0) {
      showMessage("Add at least one model node with a provider/model reference", "error");
      return;
    }
    const payload = {
      display_name: name,
      nodes,
      enabled: dialog.querySelector("#comboEnabled").checked,
    };
    try {
      const result = await api(
        isEdit ? `/admin/api/combos/${combo.combo_id}` : "/admin/api/combos",
        {
          method: isEdit ? "PUT" : "POST",
          body: JSON.stringify(payload),
        },
      );
      showMessage(result.message || `Combo ${name} saved`, "success");
      dialog.close();
      await renderCombos();
    } catch (error) {
      showMessage(`Failed to save combo: ${error.message}`, "error");
    }
  });

  document.body.appendChild(dialog);
  dialog.showModal();
}

async function removeCombo(combo) {
  if (!window.confirm(`Delete fallback combo "${combo.display_name}"?`)) return;
  try {
    const result = await api(`/admin/api/combos/${combo.combo_id}`, {
      method: "DELETE",
    });
    showMessage(result.message || "Combo deleted", "success");
    await renderCombos();
  } catch (error) {
    showMessage(`Failed to delete combo: ${error.message}`, "error");
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Add provider buttons
const addOpenAIProviderBtn = byId("addOpenAIProviderBtn");
if (addOpenAIProviderBtn) {
  addOpenAIProviderBtn.addEventListener("click", () => {
    showCustomProviderDialog('openai');
  });
}

const addComboBtn = byId("addComboBtn");
if (addComboBtn) {
  addComboBtn.addEventListener("click", () => {
    showComboDialog(undefined);
  });
}

const addAnthropicProviderBtn = byId("addAnthropicProviderBtn");
if (addAnthropicProviderBtn) {
  addAnthropicProviderBtn.addEventListener("click", () => {
    showCustomProviderDialog('anthropic');
  });
}

load().catch((error) => {
  showMessage(error.message, "error");
});
