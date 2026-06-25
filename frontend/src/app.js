import { api } from "./api.js";

const state = {
  systems: [],
  accounts: [],
  logs: [],
  chromeProfiles: [],
  selectedSystemId: "",
  selectedAccountId: "",
  browserMode: "normal",
  selectedChromeProfileDirectory: "",
  roleFilter: "",
  search: "",
  editingSystemId: "",
  editingAccountId: "",
  pendingReleaseAccountId: "",
};

const els = {
  systemList: document.querySelector("#systemList"),
  systemSearch: document.querySelector("#systemSearch"),
  systemTitle: document.querySelector("#systemTitle"),
  systemSummary: document.querySelector("#systemSummary"),
  accountGrid: document.querySelector("#accountGrid"),
  accountHint: document.querySelector("#accountHint"),
  roleFilter: document.querySelector("#roleFilter"),
  statusText: document.querySelector("#statusText"),
  guestCount: document.querySelector("#guestCount"),
  logList: document.querySelector("#logList"),
  clearLogsButton: document.querySelector("#clearLogsButton"),
  openLoginButton: document.querySelector("#openLoginButton"),
  chromeProfileField: document.querySelector("#chromeProfileField"),
  chromeProfileSelect: document.querySelector("#chromeProfileSelect"),
  releaseDialog: document.querySelector("#releaseDialog"),
  releaseDetails: document.querySelector("#releaseDetails"),
  confirmReleaseButton: document.querySelector("#confirmReleaseButton"),
  fillDialog: document.querySelector("#fillDialog"),
  fillDetails: document.querySelector("#fillDetails"),
  fillDialogClose: document.querySelector("#fillDialogClose"),
  fillDialogCancel: document.querySelector("#fillDialogCancel"),
  fillDialogConfirm: document.querySelector("#fillDialogConfirm"),
  systemDialog: document.querySelector("#systemDialog"),
  systemForm: document.querySelector("#systemForm"),
  systemDialogTitle: document.querySelector("#systemDialogTitle"),
  accountDialog: document.querySelector("#accountDialog"),
  accountDialogTitle: document.querySelector("#accountDialogTitle"),
  accountForm: document.querySelector("#accountForm"),
  toastRegion: document.querySelector("#toastRegion"),
  openSystemDialog: document.querySelector("#openSystemDialog"),
  openAccountDialog: document.querySelector("#openAccountDialog"),
  deleteAccountButton: document.querySelector("#deleteAccountButton"),
  editSystemButton: document.querySelector("#editSystemButton"),
  deleteSystemButton: document.querySelector("#deleteSystemButton"),
  toggleSidebarButton: document.querySelector("#toggleSidebarButton"),
};

const statusMeta = {
  idle: { label: "空闲", tone: "idle" },
  active: { label: "使用中", tone: "active" },
  locked: { label: "被占用", tone: "locked" },
};

const modeLabels = {
  normal: "普通页签",
  guest: "访客模式",
  incognito: "无痕模式",
  profile: "个人资料",
};

const fillTerminalStatuses = new Set(["failed", "released"]);
const fillProcessDoneStatuses = new Set(["ready", "fallback"]);
const fillPolls = new Map();

async function init() {
  const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
  if (isCollapsed) {
    document.querySelector('.app-shell').classList.add('is-collapsed');
  }

  bindEvents();
  await refreshAll();
  window.setInterval(refreshGuestSessions, 5000);
  document.querySelectorAll('select').forEach(syncCustomSelect);
}

function bindEvents() {
  els.toggleSidebarButton.addEventListener('click', () => {
    const shell = document.querySelector('.app-shell');
    const isNowCollapsed = shell.classList.toggle('is-collapsed');
    localStorage.setItem('sidebar-collapsed', isNowCollapsed);
  });

  els.systemSearch.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderSystems();
  });

  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      state.browserMode = button.dataset.mode;
      document.querySelectorAll(".segment").forEach((item) => {
        item.classList.toggle("is-active", item.dataset.mode === state.browserMode);
      });
      renderBrowserModeControls();
      renderStatusbar();
    });
  });

  els.chromeProfileSelect.addEventListener("change", (event) => {
    state.selectedChromeProfileDirectory = event.target.value;
    renderStatusbar();
  });

  els.roleFilter.addEventListener("change", (event) => {
    state.roleFilter = event.target.value;
    renderAccounts();
  });

  els.confirmReleaseButton.addEventListener("click", confirmRelease);
  els.clearLogsButton.addEventListener("click", clearLogs);
  els.openLoginButton.addEventListener("click", openLoginPage);
  els.releaseDialog.addEventListener("close", () => {
    if (els.releaseDialog.returnValue === "cancel") {
      state.pendingReleaseAccountId = "";
    }
  });

  // Fill dialog events
  els.fillDialogClose.addEventListener("click", closeFillDialog);
  els.fillDialogCancel.addEventListener("click", closeFillDialog);
  els.fillDialogConfirm.addEventListener("click", confirmFill);

  els.openSystemDialog.addEventListener("click", () => openSystemForm());
  els.editSystemButton.addEventListener("click", () => openSystemForm(currentSystem()));
  els.deleteSystemButton.addEventListener("click", deleteCurrentSystem);
  els.openAccountDialog.addEventListener("click", () => openAccountForm());
  els.deleteAccountButton.addEventListener("click", deleteSelectedAccount);

  els.systemForm.addEventListener("submit", saveSystem);
  els.accountForm.addEventListener("submit", saveAccount);

  // Password visibility toggle
  const toggleBtn = els.accountForm.querySelector(".password-toggle");
  const pwdInput = els.accountForm.elements.password;
  const eyeOpen = toggleBtn.querySelector(".eye-open");
  const eyeClosed = toggleBtn.querySelector(".eye-closed");

  toggleBtn.addEventListener("click", () => {
    const isPassword = pwdInput.type === "password";
    pwdInput.type = isPassword ? "text" : "password";
    eyeOpen.style.display = isPassword ? "none" : "";
    eyeClosed.style.display = isPassword ? "" : "none";
    toggleBtn.setAttribute("aria-label", isPassword ? "隐藏密码" : "显示密码");
    pwdInput.focus();
  });
}

async function refreshAll() {
  try {
    await api.health();
    await loadChromeProfiles();
    await loadSystems();
    await refreshGuestSessions();
    await loadLogs();
    renderStatus("本地服务已连接");
  } catch (error) {
    renderStatus(error.message);
    toast(error.message, "error");
  }
}

async function loadChromeProfiles() {
  const payload = await api.chromeProfiles();
  state.chromeProfiles = payload.profiles || [];
  if (!state.selectedChromeProfileDirectory && state.chromeProfiles.length) {
    state.selectedChromeProfileDirectory = state.chromeProfiles[0].directory;
  }
  renderProfileOptions();
}

async function loadSystems() {
  const payload = await api.systems();
  state.systems = payload.systems;
  if (!state.selectedSystemId && state.systems.length > 0) {
    state.selectedSystemId = state.systems[0].id;
  }
  renderSystems();
  await loadAccounts();
}

function renderProfileOptions() {
  els.chromeProfileSelect.innerHTML = state.chromeProfiles
    .map((profile) => {
      const label = profile.name === profile.directory
        ? profile.name
        : `${profile.name}（${profile.directory}）`;
      return `<option value="${escapeHtml(profile.directory)}">${escapeHtml(label)}</option>`;
    })
    .join("");
  els.chromeProfileSelect.value = state.selectedChromeProfileDirectory;
  syncCustomSelect(els.chromeProfileSelect);
  renderBrowserModeControls();
}

function renderBrowserModeControls() {
  const isProfileMode = state.browserMode === "profile";
  els.chromeProfileField.hidden = !isProfileMode;
  const wrapper = els.chromeProfileSelect.nextElementSibling;
  if (wrapper?.classList.contains("custom-select-wrapper")) {
    wrapper.hidden = !isProfileMode;
  }
}

async function loadAccounts() {
  if (!state.selectedSystemId) {
    state.accounts = [];
    renderCurrentSystem();
    renderAccounts();
    return;
  }
  const payload = await api.accounts(state.selectedSystemId);
  state.accounts = payload.accounts;
  if (!state.accounts.some((account) => account.id === state.selectedAccountId)) {
    state.selectedAccountId = "";
  }
  renderCurrentSystem();
  renderRoleFilter();
  renderAccounts();
  renderStatusbar();
}

async function loadLogs() {
  const payload = await api.logs();
  state.logs = payload.logs;
  renderLogs();
}

async function refreshGuestSessions() {
  const payload = await api.guestSessions();
  els.guestCount.textContent = `当前访客会话：${payload.guest_sessions} 个`;
}

function renderSystems() {
  const query = state.search.toLowerCase();
  const systems = state.systems.filter((system) => {
    return !query || `${system.name} ${system.env_tag}`.toLowerCase().includes(query);
  });

  els.systemList.innerHTML = systems
    .map((system) => {
      const active = system.id === state.selectedSystemId ? "is-active" : "";
      return `
        <button class="system-item ${active}" data-system-id="${system.id}" type="button">
          <span class="system-icon">${escapeHtml(system.name.charAt(0).toUpperCase())}</span>
          <span class="system-text">
            <strong>${escapeHtml(system.name)}</strong>
            <small>${envLabel(system.env_tag)}</small>
          </span>
          <span class="count-badge">${system.account_count || 0}</span>
        </button>
      `;
    })
    .join("");

  els.systemList.querySelectorAll(".system-item").forEach((button) => {
    button.addEventListener("click", async () => {
      if (state.selectedSystemId === button.dataset.systemId) return;
      state.selectedSystemId = button.dataset.systemId;
      state.selectedAccountId = "";
      els.systemList.querySelectorAll(".system-item").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.systemId === state.selectedSystemId);
      });
      await loadAccounts();
    });
  });
}

function renderCurrentSystem() {
  const system = currentSystem();
  if (!system) {
    els.systemTitle.textContent = "暂无系统";
    els.systemSummary.innerHTML = emptyState("先新增一个系统，再录入账号。");
    return;
  }
  els.systemTitle.textContent = system.name;
  els.systemSummary.innerHTML = `
    <div class="summary-cell">
      <span>登录页</span>
      <div class="url-with-link">
        <strong>${escapeHtml(system.login_url)}</strong>
        <a href="${escapeHtml(system.login_url)}" target="_blank" rel="noopener noreferrer" class="external-link-btn" title="在新标签页中打开">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
        </a>
      </div>
    </div>
    <div class="summary-cell compact">
      <span>环境</span>
      <strong>${envLabel(system.env_tag)}</strong>
    </div>
    <div class="summary-cell compact">
      <span>账号</span>
      <strong>${system.account_count || state.accounts.length}</strong>
    </div>
    <div class="summary-cell">
      <span>备注</span>
      <strong>${escapeHtml(system.note || "无")}</strong>
    </div>
  `;
}

function renderRoleFilter() {
  const roles = Array.from(new Set(state.accounts.map((account) => account.role_label))).sort();
  els.roleFilter.innerHTML =
    `<option value="">全部角色</option>` +
    roles.map((role) => `<option value="${escapeHtml(role)}">${escapeHtml(role)}</option>`).join("");
  els.roleFilter.value = state.roleFilter;
  syncCustomSelect(els.roleFilter);
}

function renderAccounts() {
  const visible = state.accounts.filter((account) => {
    return !state.roleFilter || account.role_label === state.roleFilter;
  });
  els.accountHint.textContent = `${visible.length} 个账号，${state.accounts.filter((item) => item.status === "idle").length} 个空闲`;

  // 根据选中状态显示/隐藏删除按钮
  const selectedAccount = currentAccount();
  els.deleteAccountButton.style.display = selectedAccount ? "" : "none";

  if (!visible.length) {
    els.accountGrid.innerHTML = emptyState("当前筛选下没有账号。");
    renderStatusbar();
    return;
  }

  els.accountGrid.innerHTML = visible
    .map((account) => {
      const selected = account.id === state.selectedAccountId ? "is-selected" : "";
      const meta = statusMeta[account.status] || statusMeta.locked;
      const disabled = account.status !== "idle" ? "aria-disabled=\"true\"" : "";
      const action =
        account.status === "active"
          ? `<button class="link-button" data-release="${account.id}" type="button">释放</button>`
          : account.status === "locked"
            ? `<button class="link-button" data-unlock="${account.id}" type="button">解除占用</button>`
            : `<button class="link-button" data-lock="${account.id}" type="button">标记占用</button>`;
      const fillBtn =
        account.status === "idle"
          ? `<button class="fill-button" data-fill="${account.id}" type="button">填充并跳转</button>`
          : "";
      const editBtn =
        account.status === "idle"
          ? `<button class="card-edit-btn" data-edit-account="${account.id}" type="button" title="编辑账号">✏️</button>`
          : "";
      return `
        <article class="account-card ${selected}" data-account-id="${account.id}" ${disabled}>
          ${editBtn}
          <div class="card-topline">
            <span class="role-label">${escapeHtml(account.role_label)}</span>
            <span class="status-badge ${meta.tone}">${meta.label}</span>
          </div>
          <h3>${escapeHtml(account.display_name)}</h3>
          <p class="username">${escapeHtml(account.username)}</p>
          <div class="card-actions">${action}${fillBtn}</div>
        </article>
      `;
    })
    .join("");

  els.accountGrid.querySelectorAll(".account-card").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      const account = state.accounts.find((item) => item.id === card.dataset.accountId);
      if (!account) return;
      if (account.status !== "idle") {
        toast(account.status === "active" ? "该账号正在使用中" : "该账号已被负责人标记为占用", "warn");
        return;
      }
      state.selectedAccountId = account.id;
      els.accountGrid.querySelectorAll(".account-card").forEach((c) => {
        c.classList.toggle("is-selected", c.dataset.accountId === state.selectedAccountId);
      });
      els.deleteAccountButton.style.display = currentAccount() ? "" : "none";
    });
  });

  els.accountGrid.querySelectorAll("[data-release]").forEach((button) => {
    button.addEventListener("click", () => openReleaseDialog(button.dataset.release));
  });
  els.accountGrid.querySelectorAll("[data-lock]").forEach((button) => {
    button.addEventListener("click", () => setAccountLock(button.dataset.lock, true));
  });
  els.accountGrid.querySelectorAll("[data-unlock]").forEach((button) => {
    button.addEventListener("click", () => setAccountLock(button.dataset.unlock, false));
  });
  els.accountGrid.querySelectorAll("[data-edit-account]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openAccountForm(button.dataset.editAccount);
    });
  });
  els.accountGrid.querySelectorAll("[data-fill]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openFillDialog(button.dataset.fill);
    });
  });

  renderStatusbar();
}

function renderLogs() {
  if (!state.logs.length) {
    els.logList.innerHTML = emptyState("暂无操作日志。");
    return;
  }
  els.logList.innerHTML = state.logs
    .map((log) => {
      return `
        <div class="log-item">
          <span>${escapeHtml(log.action)}</span>
          <strong>${escapeHtml(log.message)}</strong>
          <time>${formatTime(log.created_at)}</time>
        </div>
      `;
    })
    .join("");
}

async function clearLogs() {
  if (!state.logs.length) return;
  els.clearLogsButton.disabled = true;
  try {
    await api.clearLogs();
    state.logs = [];
    renderLogs();
  } catch (err) {
    renderStatus(err.message);
  } finally {
    els.clearLogsButton.disabled = false;
  }
}

function renderStatusbar() {
  const system = currentSystem();
  if (!system) {
    els.openLoginButton.disabled = true;
    renderStatus("请先新增系统");
  } else {
    const needsProfile = state.browserMode === "profile";
    const hasProfile = Boolean(state.selectedChromeProfileDirectory);
    els.openLoginButton.disabled = needsProfile && !hasProfile;
    const count = state.accounts.filter((item) => item.status === "idle").length;
    const profile = currentChromeProfile();
    const modeText = needsProfile && profile
      ? `${modeLabels[state.browserMode]}：${profile.name}`
      : modeLabels[state.browserMode];
    renderStatus(`${system.name} · ${count} 个空闲账号 · ${modeText}`);
  }
}

function renderStatus(text) {
  els.statusText.textContent = text;
}

async function openLoginPage() {
  const system = currentSystem();
  if (!system) return;
  els.openLoginButton.disabled = true;
  els.openLoginButton.textContent = "正在打开...";
  try {
    const payloadData = {
      system_id: system.id,
      browser_mode: state.browserMode,
    };
    if (state.browserMode === "profile") {
      payloadData.chrome_profile_directory = state.selectedChromeProfileDirectory;
    }
    const payload = await api.openLogin({
      ...payloadData,
    });
    toast(payload.open_login.message, "success");
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    els.openLoginButton.disabled = false;
    els.openLoginButton.textContent = "打开登录页";
  }
}

function openFillDialog(accountId) {
  const system = currentSystem();
  const account = state.accounts.find((item) => item.id === accountId);
  if (!system || !account) return;
  if (account.status !== "idle") {
    toast(account.status === "active" ? "该账号正在使用中" : "该账号已被负责人标记为占用", "warn");
    return;
  }
  state.selectedAccountId = accountId;
  els.fillDetails.innerHTML = `
    <div><dt>目标系统</dt><dd>${escapeHtml(system.name)}</dd></div>
    <div><dt>环境</dt><dd>${envLabel(system.env_tag)}</dd></div>
    <div><dt>登录页</dt><dd>${escapeHtml(system.login_url)}</dd></div>
    <div><dt>账号</dt><dd>${escapeHtml(account.display_name)}</dd></div>
    <div><dt>用户名</dt><dd>${escapeHtml(account.username)}</dd></div>
    <div><dt>密码</dt><dd>••••••••</dd></div>
    <div><dt>浏览器模式</dt><dd>${modeLabels[state.browserMode] || state.browserMode}</dd></div>
  `;
  els.fillDialogConfirm.disabled = false;
  els.fillDialogConfirm.innerHTML = `
    <span class="btn-icon" style="margin-right: 4px;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    </span>
    确认填充
  `;
  els.fillDialog.showModal();
}

function closeFillDialog() {
  els.fillDialog.close();
}

async function confirmFill() {
  const system = currentSystem();
  const account = currentAccount();
  if (!system || !account) return;
  els.fillDialogConfirm.disabled = true;
  els.fillDialogConfirm.textContent = "正在填充…";
  try {
    const payloadData = {
      system_id: system.id,
      account_id: account.id,
      browser_mode: state.browserMode,
    };
    if (state.browserMode === "profile") {
      payloadData.chrome_profile_directory = state.selectedChromeProfileDirectory;
    }
    const payload = await api.fill(payloadData);
    els.fillDialog.close();
    toast(payload.fill.message || "填充任务已启动", "success");
    if (payload.fill.session_id) {
      pollFillSession(payload.fill.session_id);
    }
    await loadAccounts();
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
    els.fillDialogConfirm.disabled = false;
    els.fillDialogConfirm.innerHTML = `
      <span class="btn-icon" style="margin-right: 4px;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
      </span>
      确认填充
    `;
  }
}

function pollFillSession(sessionId, attempt = 0, hasNotifiedProcessDone = false) {
  if (fillPolls.has(sessionId)) {
    window.clearTimeout(fillPolls.get(sessionId));
  }
  const timer = window.setTimeout(async () => {
    try {
      const payload = await api.session(sessionId);
      const session = payload.session;
      if (fillTerminalStatuses.has(session.status)) {
        fillPolls.delete(sessionId);
        if (session.message) {
          const tone = session.status === "failed" ? "error" : "success";
          toast(session.message, tone);
        }
        await loadAccounts();
        await refreshGuestSessions();
        await loadLogs();
        return;
      }
      let notifiedProcessDone = hasNotifiedProcessDone;
      if (!notifiedProcessDone && fillProcessDoneStatuses.has(session.status)) {
        notifiedProcessDone = true;
        if (session.message) {
          toast(session.message, session.status === "fallback" ? "warn" : "success");
        }
        await loadAccounts();
        await refreshGuestSessions();
        await loadLogs();
      }
      if (attempt >= 720) {
        fillPolls.delete(sessionId);
        toast("会话仍在使用中，请需要时手动刷新查看账号状态", "warn");
        await loadAccounts();
        return;
      }
      pollFillSession(sessionId, attempt + 1, notifiedProcessDone);
    } catch (error) {
      fillPolls.delete(sessionId);
      toast(error.message, "error");
      await loadAccounts();
    }
  }, attempt === 0 ? 800 : hasNotifiedProcessDone ? 5000 : 1500);
  fillPolls.set(sessionId, timer);
}

function openReleaseDialog(accountId) {
  const system = currentSystem();
  const account = state.accounts.find((item) => item.id === accountId);
  if (!system || !account) return;
  state.pendingReleaseAccountId = accountId;
  els.releaseDetails.innerHTML = `
    <div><dt>目标系统</dt><dd>${escapeHtml(system.name)}</dd></div>
    <div><dt>账号</dt><dd>${escapeHtml(account.display_name)}</dd></div>
    <div><dt>用户名</dt><dd>${escapeHtml(account.username)}</dd></div>
    <div><dt>当前状态</dt><dd>${statusMeta[account.status]?.label || account.status}</dd></div>
  `;
  els.confirmReleaseButton.disabled = false;
  els.confirmReleaseButton.textContent = "确认释放";
  els.releaseDialog.showModal();
}

async function confirmRelease() {
  if (!state.pendingReleaseAccountId) return;
  els.confirmReleaseButton.disabled = true;
  els.confirmReleaseButton.textContent = "正在释放...";
  await releaseAccount(state.pendingReleaseAccountId);
  state.pendingReleaseAccountId = "";
  els.releaseDialog.close();
}

function openSystemForm(system = null) {
  state.editingSystemId = system?.id || "";
  els.systemDialogTitle.textContent = system ? "编辑系统" : "新增系统";
  els.systemForm.reset();
  if (system) {
    els.systemForm.elements.name.value = system.name;
    els.systemForm.elements.env_tag.value = system.env_tag;
    els.systemForm.elements.login_url.value = system.login_url;
    els.systemForm.elements.note.value = system.note || "";
  }
  syncCustomSelect(els.systemForm.elements.env_tag);
  els.systemDialog.showModal();
}

async function saveSystem(event) {
  event.preventDefault();
  if (event.submitter?.value === "cancel") {
    els.systemDialog.close();
    return;
  }
  const form = new FormData(els.systemForm);
  const data = Object.fromEntries(form.entries());
  try {
    if (state.editingSystemId) {
      await api.updateSystem(state.editingSystemId, data);
      toast("系统已更新", "success");
    } else {
      const payload = await api.createSystem(data);
      state.selectedSystemId = payload.system.id;
      toast("系统已新增", "success");
    }
    els.systemDialog.close();
    await loadSystems();
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function deleteCurrentSystem() {
  const system = currentSystem();
  if (!system) return;
  const confirmed = await confirmAction(`确认删除系统「${system.name}」？此操作无法撤销。`);
  if (!confirmed) return;
  try {
    await api.deleteSystem(system.id);
    state.selectedSystemId = "";
    toast("系统已删除", "success");
    await loadSystems();
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function deleteSelectedAccount() {
  const account = currentAccount();
  if (!account) return;
  const confirmed = await confirmAction(`确认删除账号「${account.display_name}」？`);
  if (!confirmed) return;
  try {
    await api.deleteAccount(account.id);
    state.selectedAccountId = "";
    toast("账号已删除", "success");
    await loadAccounts();
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function saveAccount(event) {
  event.preventDefault();
  if (event.submitter?.value === "cancel") {
    els.accountDialog.close();
    return;
  }
  const system = currentSystem();
  if (!system) return;
  const form = new FormData(els.accountForm);
  const data = Object.fromEntries(form.entries());
  try {
    if (state.editingAccountId) {
      await api.updateAccount(state.editingAccountId, data);
      toast("账号已更新", "success");
    } else {
      await api.createAccount(system.id, data);
      toast("账号已新增", "success");
    }
    els.accountDialog.close();
    await loadSystems();
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
  }
}

function openAccountForm(accountId = "") {
  state.editingAccountId = accountId;
  els.accountForm.reset();

  // Reset password visibility to hidden
  const pwdInput = els.accountForm.elements.password;
  pwdInput.type = "password";
  const toggleBtn = els.accountForm.querySelector(".password-toggle");
  toggleBtn.querySelector(".eye-open").style.display = "";
  toggleBtn.querySelector(".eye-closed").style.display = "none";
  toggleBtn.setAttribute("aria-label", "显示密码");

  if (accountId) {
    const account = state.accounts.find((a) => a.id === accountId);
    if (!account) return;
    els.accountDialogTitle.textContent = "编辑账号";
    els.accountForm.elements.role_label.value = account.role_label;
    els.accountForm.elements.display_name.value = account.display_name;
    els.accountForm.elements.username.value = account.username;
    els.accountForm.elements.password.value = "";
    els.accountForm.elements.password.removeAttribute("required");
  } else {
    els.accountDialogTitle.textContent = "新增账号";
    els.accountForm.elements.password.setAttribute("required", "");
  }
  els.accountDialog.showModal();
}

async function releaseAccount(accountId) {
  try {
    await api.release(accountId);
    toast("账号已释放", "success");
    await loadSystems();
    await loadLogs();
    await refreshGuestSessions();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function setAccountLock(accountId, locked) {
  try {
    await api.lock(accountId, locked);
    toast(locked ? "账号已标记为被占用" : "账号已恢复空闲", "success");
    await loadSystems();
    await loadLogs();
  } catch (error) {
    toast(error.message, "error");
  }
}

function currentSystem() {
  return state.systems.find((system) => system.id === state.selectedSystemId);
}

function currentAccount() {
  return state.accounts.find((account) => account.id === state.selectedAccountId);
}

function currentChromeProfile() {
  return state.chromeProfiles.find((profile) => {
    return profile.directory === state.selectedChromeProfileDirectory;
  });
}

function envLabel(env) {
  return { TEST: "测试", UAT: "UAT", PRE: "预发布" }[env] || env;
}

function emptyState(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function syncCustomSelect(selectEl) {
  selectEl.style.display = 'none';

  let wrapper = selectEl.nextElementSibling;
  if (!wrapper || !wrapper.classList.contains('custom-select-wrapper')) {
    wrapper = document.createElement('div');
    wrapper.className = 'custom-select-wrapper';
    selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);
    
    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target) && e.target !== selectEl) {
        wrapper.classList.remove('is-open');
      }
    });
  }

  const options = Array.from(selectEl.options);
  const selectedOption = options.find(o => o.selected) || options[0];
  const selectedText = selectedOption ? selectedOption.textContent : '';

  wrapper.innerHTML = `
    <div class="custom-select-trigger" tabindex="0">${escapeHtml(selectedText)}</div>
    <ul class="custom-select-options">
      ${options.map((opt, index) => {
        const isSelected = opt.selected ? 'is-selected' : '';
        return `<li class="custom-select-option ${isSelected}" data-index="${index}">${escapeHtml(opt.textContent)}</li>`;
      }).join('')}
    </ul>
  `;

  const trigger = wrapper.querySelector('.custom-select-trigger');
  const optionNodes = wrapper.querySelectorAll('.custom-select-option');

  trigger.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    document.querySelectorAll('.custom-select-wrapper.is-open').forEach(w => {
      if (w !== wrapper) w.classList.remove('is-open');
    });
    wrapper.classList.toggle('is-open');
  });

  trigger.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      wrapper.classList.toggle('is-open');
    }
  });

  optionNodes.forEach(node => {
    node.addEventListener('click', (e) => {
      e.stopPropagation();
      const idx = parseInt(node.dataset.index, 10);
      selectEl.selectedIndex = idx;
      wrapper.classList.remove('is-open');
      selectEl.dispatchEvent(new Event('change', { bubbles: true }));
      syncCustomSelect(selectEl);
    });
  });
}

function toast(message, type = "info") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  els.toastRegion.append(node);
  window.setTimeout(() => node.remove(), 3200);
}

function confirmAction(message) {
  return new Promise((resolve) => {
    const dialog = document.getElementById("confirmDialog");
    const msgEl = document.getElementById("confirmDialogMessage");
    const confirmBtn = document.getElementById("confirmDialogConfirm");
    const cancelBtn = document.getElementById("confirmDialogCancel");

    msgEl.textContent = message;

    const cleanup = () => {
      confirmBtn.removeEventListener("click", onConfirm);
      cancelBtn.removeEventListener("click", onCancel);
      dialog.removeEventListener("cancel", onCancel);
      dialog.close();
    };

    const onConfirm = () => {
      cleanup();
      resolve(true);
    };

    const onCancel = (e) => {
      e.preventDefault();
      cleanup();
      resolve(false);
    };

    confirmBtn.addEventListener("click", onConfirm);
    cancelBtn.addEventListener("click", onCancel);
    dialog.addEventListener("cancel", onCancel);

    dialog.showModal();
  });
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

init();
