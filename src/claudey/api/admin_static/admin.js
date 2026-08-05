const state = {
  config: null,
  fields: new Map(),
  localStatus: new Map(),
  modelOptions: [],
  modelComboboxes: new Set(),
  authPollers: new Map(),
  activeView: "providers",
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
    FCC_ENV_FILE: "HANS_ENV_FILE",
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
  renderNav();
  renderProviders(config.provider_status);
  renderOnboarding(config.provider_status);
  renderGreeting();
  renderSections(config.sections, config.fields);
  renderServerStatus();
  byId("configPath").textContent = config.paths.managed;
  await refreshConnectedAccounts();
  await hydrateModelOptions();
  await validate(false);
  await refreshLocalStatus();
  updateDirtyState();
  showMessage("");
}

function renderGreeting() {
  const el = byId("welcomeGreeting");
  if (!el) return;
  const seed = Math.floor(Date.now() / 3600000);
  const index = (seed + WELCOME_GREETINGS.length) % WELCOME_GREETINGS.length;
  el.textContent = WELCOME_GREETINGS[Math.abs(index)];
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

    const actions = document.createElement("div");
    actions.className = "provider-actions";

    const isConfigured = ["configured", "reachable"].includes(provider.status);
    const primaryField = providerPrimaryFieldKey(provider);
    const fieldDesc =
      (primaryField && state.fields.get(primaryField)?.description) || "";

    if (isConfigured) {
      const badge = document.createElement("span");
      badge.className = "configured-badge";
      const check = document.createElement("span");
      check.className = "configured-check";
      check.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>`;
      badge.append(check, "Configured");
      actions.appendChild(badge);
    } else {
      const configure = document.createElement("button");
      configure.type = "button";
      configure.className = "secondary-button card-configure";
      configure.textContent = "Configure";
      configure.addEventListener("click", () => scrollToField(primaryField));
      actions.appendChild(configure);
    }

    if (isConfigured) {
      const switchBtn = document.createElement("button");
      switchBtn.type = "button";
      switchBtn.className = "secondary-button";
      switchBtn.textContent = "Switch key";
      switchBtn.addEventListener("click", () => scrollToField(primaryField));
      actions.appendChild(switchBtn);
    } else {
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
    disconnected: "Not connected",
    connecting: "Connecting",
    connected: "Connected",
    error: "Needs attention",
  };
  return labels[status.state] || status.label || "Not connected";
}

function connectedAccountMeta(status) {
  if (status.connected) {
    const identity = status.email || "ChatGPT subscription connected";
    const models = Number.isInteger(status.model_count)
      ? `${status.model_count} model${status.model_count === 1 ? "" : "s"} available. `
      : "";
    const error = status.message ? `${status.message} ` : "";
    return `${identity}. ${models}${error}Restart your agent to refresh its model picker.`;
  }
  if (status.mode === "device" && status.user_code) {
    return `Enter code ${status.user_code} at ${status.verification_url}`;
  }
  if (status.state === "connecting") {
    return "Finish signing in, then return to this page.";
  }
  if (status.state === "error") {
    const detail = status.message ? ` - ${status.message}` : "";
    return `Something went wrong${detail}. Try disconnecting, then connect again.`;
  }
  return status.message || "Connect a ChatGPT account to discover subscription models.";
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

function pollConnectedAccount(provider) {
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
  if (field.description) {
    const description = document.createElement("div");
    description.className = "field-description";
    description.textContent = field.description;
    wrapper.appendChild(description);
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
    showMessage("Applied. Restarting server...", "ok");
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
  const toast = document.createElement("div");
  toast.className = `toast${kind ? ` toast-${kind}` : ""}`;
  toast.setAttribute("role", "status");
  const icon = document.createElement("span");
  icon.className = "toast-icon";
  icon.innerHTML = kind === "ok" ? ICON_CHECK : kind === "error" ? ICON_ALERT : ICON_INFO;
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
  window.setTimeout(remove, 4000);
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
      pill.className = "server-status ok";
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

const sidebarToggle = byId("sidebarToggle");
const sectionNav = byId("sectionNav");
const mobileQuery = window.matchMedia("(max-width: 900px)");

function applySidebarCollapsed(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
  sidebarToggle.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
  sectionNav.inert = collapsed && mobileQuery.matches;
  localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? "collapsed" : "expanded");
}

sidebarToggle.addEventListener("click", () => {
  applySidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
});

mobileQuery.addEventListener("change", (event) => {
  sectionNav.inert = event.matches && document.body.classList.contains("sidebar-collapsed");
});

applySidebarCollapsed(localStorage.getItem(SIDEBAR_STATE_KEY) === "collapsed");

document.addEventListener("pointerdown", (event) => {

  state.modelComboboxes.forEach((combobox) => {
    if (combobox.isOpen && !combobox.element.contains(event.target)) combobox.close();
  });
});

load().catch((error) => {
  showMessage(error.message, "error");
});
