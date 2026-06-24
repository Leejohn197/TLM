import { api } from "./api.js";

const state = {
  systems: [],
  accounts: [],
  logs: [],
  selectedSystemId: "",
  selectedAccountId: "",
  browserMode: "normal",
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
  releaseDialog: document.querySelector("#releaseDialog"),
  releaseDetails: document.querySelector("#releaseDetails"),
  confirmReleaseButton: document.querySelector("#confirmReleaseButton"),
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
};

const statusMeta = {
  idle: { label: "空闲", tone: "idle" },
  active: { label: "使用中", tone: "active" },
  locked: { label: "被占用", tone: "locked" },
};

async function init() {
  bindEvents();
  await refreshAll();
  window.setInterval(refreshGuestSessions, 5000);
}

function bindEvents() {
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
      renderStatusbar();
    });
  });

  els.roleFilter.addEventListener("change", (event) => {
    state.roleFilter = event.target.value;
    renderAccounts();
  });

  els.confirmReleaseButton.addEventListener("click", confirmRelease);
  els.clearLogsButton.addEventListener("click", clearLogs);
  els.releaseDialog.addEventListener("close", () => {
    if (els.releaseDialog.returnValue === "cancel") {
      state.pendingReleaseAccountId = "";
    }
  });

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
    await loadSystems();
    await refreshGuestSessions();
    await loadLogs();
    renderStatus("本地服务已连接");
  } catch (error) {
    renderStatus(error.message);
    toast(error.message, "error");
  }
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
          <span>
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
      state.selectedSystemId = button.dataset.systemId;
      state.selectedAccountId = "";
      await loadAccounts();
      renderSystems();
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
      <strong>${escapeHtml(system.login_url)}</strong>
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
          <div class="card-actions">${action}</div>
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
      renderAccounts();
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
    renderStatus("请先新增系统");
  } else {
    const count = state.accounts.filter((item) => item.status === "idle").length;
    renderStatus(`${system.name} · ${count} 个空闲账号`);
  }
}

function renderStatus(text) {
  els.statusText.textContent = text;
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
  const confirmed = window.confirm(`确认删除「${system.name}」？`);
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
  const confirmed = window.confirm(`确认删除账号「${account.display_name}」？`);
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

function envLabel(env) {
  return { TEST: "测试", UAT: "UAT", PRE: "预发布" }[env] || env;
}

function emptyState(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function toast(message, type = "info") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  els.toastRegion.append(node);
  window.setTimeout(() => node.remove(), 3200);
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
