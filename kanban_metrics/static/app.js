const statusBox = document.getElementById("status-box");
const form = document.getElementById("config-form");
const testConnectionButton = document.getElementById("test-connection");
const validateJqlButton = document.getElementById("validate-jql");
const loadStatusesButton = document.getElementById("load-statuses");
const loadDemoButton = document.getElementById("load-demo");
const newConfigButton = document.getElementById("new-config");
const newConfigDashboardButton = document.getElementById("new-config-dashboard");
const syncButton = document.getElementById("sync-config");
const refreshButton = document.getElementById("refresh-data");
const openConfigurationButton = document.getElementById("open-configuration");
const syncStatusPanel = document.getElementById("sync-status-panel");
const syncStatusTitle = document.getElementById("sync-status-title");
const syncStatusBadge = document.getElementById("sync-status-badge");
const syncProgressBar = document.getElementById("sync-progress-bar");
const syncProgressValue = document.getElementById("sync-progress-value");
const syncProgressMessage = document.getElementById("sync-progress-message");
const syncProgressHelp = document.getElementById("sync-progress-help");
const syncFailureHelp = document.getElementById("sync-failure-help");
const syncFailureList = document.getElementById("sync-failure-list");
const cycleXStartInput = document.getElementById("cycle-x-start");
const cycleXEndInput = document.getElementById("cycle-x-end");
const cycleYMaxInput = document.getElementById("cycle-y-max");
const cycleFitP95Button = document.getElementById("cycle-fit-p95");
const cycleShowAllButton = document.getElementById("cycle-show-all");
const cycleHiddenControls = document.getElementById("cycle-hidden-controls");
const cycleHiddenCount = document.getElementById("cycle-hidden-count");
const cycleResetHiddenButton = document.getElementById("cycle-reset-hidden");
const cycleTrendChart = document.getElementById("cycle-trend-chart");
const cycleContextMenu = document.getElementById("cycle-context-menu");
const cycleHidePointButton = document.getElementById("cycle-hide-point");
const cycleTooltip = document.getElementById("cycle-tooltip");
const cycleControlsError = document.getElementById("cycle-controls-error");
const cyclePercentiles = document.getElementById("cycle-percentiles");
const throughputTooltip = document.getElementById("throughput-tooltip");
const cfdLegend = document.getElementById("cfd-legend");
const cfdHiddenControls = document.getElementById("cfd-hidden-controls");
const cfdHiddenCount = document.getElementById("cfd-hidden-count");
const cfdResetHiddenButton = document.getElementById("cfd-reset-hidden");
const cfdContextMenu = document.getElementById("cfd-context-menu");
const cfdHideStatusButton = document.getElementById("cfd-hide-status");
const throughputIntervalButtons = Array.from(document.querySelectorAll("[data-throughput-interval]"));
const configList = document.getElementById("config-list");
const mappingPreview = document.getElementById("mapping-preview");
const projectSelect = document.getElementById("project-keys");
const tabButtons = Array.from(document.querySelectorAll("[data-tab-button]"));
const tabPanels = Array.from(document.querySelectorAll("[data-tab-panel]"));

let currentConfigId = null;
let configsById = {};
let currentBoardMapping = null;
let activeTab = "dashboard";
let currentCycleData = null;
let currentThroughputData = null;
let currentPhaseRatioData = null;
let currentCfdData = null;
let currentThroughputInterval = "month";
let availableProjects = [];
let statusBuckets = { inactive: [], active: [], done: [] };
let statusCatalog = {};
let draggedStatusId = null;
let activeSyncJobId = null;
let hiddenIssueKeysByConfigId = {};
let cycleContextIssueKey = null;
let hiddenCfdSeriesByConfigId = {};
let cfdContextSeriesName = null;

function writeStatus(message, payload) {
  statusBox.textContent = payload ? `${message}\n\n${JSON.stringify(payload, null, 2)}` : message;
}

function hiddenIssueKeysForCurrentConfig() {
  if (!currentConfigId) {
    return new Set();
  }
  if (!hiddenIssueKeysByConfigId[currentConfigId]) {
    hiddenIssueKeysByConfigId[currentConfigId] = new Set();
  }
  return hiddenIssueKeysByConfigId[currentConfigId];
}

function hiddenCfdSeriesForCurrentConfig() {
  if (!currentConfigId) {
    return new Set();
  }
  if (!hiddenCfdSeriesByConfigId[currentConfigId]) {
    hiddenCfdSeriesByConfigId[currentConfigId] = new Set();
  }
  return hiddenCfdSeriesByConfigId[currentConfigId];
}

function hiddenIssueCountForCurrentConfig() {
  return hiddenIssueKeysForCurrentConfig().size;
}

function isIssueHidden(issueKey) {
  return hiddenIssueKeysForCurrentConfig().has(issueKey);
}

function visibleCycleIssues(issues) {
  return (issues || []).filter((issue) => !isIssueHidden(issue.issueKey));
}

function syncTitleForState(state) {
  if (state === "running") {
    return "Synchronization in progress";
  }
  if (state === "completed") {
    return "Synchronization completed";
  }
  if (state === "failed") {
    return "Synchronization failed";
  }
  return "No sync running";
}

function syncBadgeForState(state) {
  if (state === "running") {
    return "Running";
  }
  if (state === "completed") {
    return "Done";
  }
  if (state === "failed") {
    return "Failed";
  }
  return "Idle";
}

function syncHelpForState(state, message = "") {
  if (state === "running") {
    return "Keep this tab open while issues and changelog history are being loaded from Jira.";
  }
  if (state === "completed") {
    return "The dashboard has been refreshed with the latest synced data.";
  }
  if (state === "failed") {
    return message || "Sync stopped before completion.";
  }
  return "Start step 4 to load issues from Jira.";
}

function syncFailureSuggestions(message = "") {
  const lower = String(message || "").toLowerCase();
  const suggestions = [];

  if (/401|403|unauthor|forbidden|auth|token|permission/.test(lower)) {
    suggestions.push("Check that the Personal access token is valid and has permission to read issues and changelogs in Jira.");
  }
  if (/project|issuetype|jql|query|field/.test(lower)) {
    suggestions.push("Recheck Project key, Issue types, date range, and Extra JQL, then run step 2 again.");
  }
  if (/status|workflow|mapping/.test(lower)) {
    suggestions.push("Run step 3 again and confirm the statuses are mapped into inactive, active, and done as expected.");
  }
  if (/timed out|timeout|name or service|temporary failure|refused|ssl|certificate|connection|network/.test(lower)) {
    suggestions.push("Verify that this machine can reach the Jira Server/DC URL and that the Jira base URL is correct.");
  }
  if (/secret|credential|missing/.test(lower)) {
    suggestions.push("Save the configuration again and make sure the token field is filled before retrying the sync.");
  }

  suggestions.push("Open the status box below for the raw backend response if you need the exact technical error.");
  return [...new Set(suggestions)];
}

function setSyncStatus(state, options = {}) {
  const progress = Math.max(0, Math.min(100, Math.round((options.progress ?? 0) * 100)));
  const message = options.message || "";
  const suggestions = options.suggestions || [];

  syncStatusPanel.dataset.state = state;
  syncStatusTitle.textContent = options.title || syncTitleForState(state);
  syncStatusBadge.textContent = syncBadgeForState(state);
  syncProgressBar.style.width = `${progress}%`;
  syncProgressValue.textContent = `${progress}%`;
  syncProgressMessage.textContent = message || syncHelpForState(state);
  syncProgressHelp.textContent = options.help || syncHelpForState(state, message);
  syncFailureHelp.hidden = state !== "failed";
  syncFailureList.innerHTML = suggestions.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  syncButton.disabled = state === "running";
}

function parseCsv(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function selectedProjectKeys(value) {
  const projectKey = String(value || "").trim();
  return projectKey ? [projectKey] : [];
}

function uniqueStatusEntries(entries) {
  const seen = new Set();
  return entries.filter((entry) => {
    if (!entry?.id || seen.has(entry.id)) {
      return false;
    }
    seen.add(entry.id);
    return true;
  });
}

function statusNameForId(statusId) {
  return statusCatalog[statusId]?.name || currentBoardMapping?.status_names?.[statusId] || statusId;
}

function statusEntriesFromBuckets() {
  return {
    inactive: statusBuckets.inactive.map((statusId) => ({ id: statusId, name: statusNameForId(statusId) })),
    active: statusBuckets.active.map((statusId) => ({ id: statusId, name: statusNameForId(statusId) })),
    done: statusBuckets.done.map((statusId) => ({ id: statusId, name: statusNameForId(statusId) })),
  };
}

function buildBoardMappingFromBuckets() {
  const statusNames = Object.fromEntries(
    Object.keys(statusCatalog).map((statusId) => [statusId, statusCatalog[statusId].name || statusId])
  );
  return {
    columns: [
      { id: "inactive", name: "Inactive statuses", status_ids: [...statusBuckets.inactive] },
      { id: "active", name: "Active statuses", status_ids: [...statusBuckets.active] },
      { id: "done", name: "Done statuses", status_ids: [...statusBuckets.done] },
    ],
    phase_names: {},
    status_names: statusNames,
  };
}

function syncStatusBucketsToForm() {
  form.elements.start_status_ids.value = statusBuckets.active.join(", ");
  form.elements.active_status_ids.value = statusBuckets.active.join(", ");
  form.elements.done_status_ids.value = statusBuckets.done.join(", ");
  currentBoardMapping = buildBoardMappingFromBuckets();
}

function setStatusBuckets(nextBuckets) {
  statusBuckets = {
    inactive: [...(nextBuckets.inactive || [])],
    active: [...(nextBuckets.active || [])],
    done: [...(nextBuckets.done || [])],
  };
  syncStatusBucketsToForm();
}

function initializeStatusBucketsFromConfig(config) {
  statusCatalog = Object.fromEntries(
    Object.entries(config?.board_mapping?.status_names || {}).map(([id, name]) => [id, { id, name }])
  );
  const columns = config?.board_mapping?.columns || [];
  const inactiveColumn = columns.find((column) => column.id === "inactive")
    || columns.find((column) => /inactive|to do|todo/i.test(column.name || ""));
  const activeColumn = columns.find((column) => column.id === "active")
    || columns.find((column) => /active|in progress|doing/i.test(column.name || ""));
  const doneColumn = columns.find((column) => column.id === "done")
    || columns.find((column) => /done/i.test(column.name || ""));
  setStatusBuckets({
    inactive: inactiveColumn?.status_ids || [],
    active: config?.active_status_ids || activeColumn?.status_ids || [],
    done: config?.done_status_ids || doneColumn?.status_ids || [],
  });
}

function moveStatusToBucket(statusId, targetBucket) {
  const normalized = {
    inactive: statusBuckets.inactive.filter((id) => id !== statusId),
    active: statusBuckets.active.filter((id) => id !== statusId),
    done: statusBuckets.done.filter((id) => id !== statusId),
  };
  normalized[targetBucket].push(statusId);
  setStatusBuckets(normalized);
  renderBoardMapping(currentBoardMapping);
}

function quoteJqlLiteral(value) {
  return `"${String(value || "").replaceAll("\\", "\\\\").replaceAll('"', '\\"')}"`;
}

function listClause(fieldName, values) {
  const items = values.filter(Boolean);
  if (!items.length) {
    return "";
  }
  if (items.length === 1) {
    return `${fieldName} = ${quoteJqlLiteral(items[0])}`;
  }
  return `${fieldName} in (${items.map((item) => quoteJqlLiteral(item)).join(", ")})`;
}

function addDaysToIsoDate(value, days) {
  if (!value) {
    return "";
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function formatHours(value) {
  return `${Math.round(value)}h`;
}

function formatDuration(valueHours) {
  if (valueHours >= 24) {
    const days = valueHours / 24;
    return days >= 10 ? `${Math.round(days)}d` : `${days.toFixed(1)}d`;
  }
  return `${Math.round(valueHours)}h`;
}

function hoursToDays(valueHours) {
  return valueHours / 24;
}

function daysToHours(valueDays) {
  return valueDays * 24;
}

function roundDaysUp(valueHours) {
  return Math.max(0.1, Math.ceil(hoursToDays(valueHours) * 10) / 10);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTaskCount(value) {
  return `${value} task${value === 1 ? "" : "s"}`;
}

function padNumber(value) {
  return String(value).padStart(2, "0");
}

function throughputIntervalLabel(interval, count = 2) {
  if (interval === "week") {
    return count === 1 ? "week" : "weeks";
  }
  return count === 1 ? "month" : "months";
}

function syncThroughputIntervalControls() {
  throughputIntervalButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.throughputInterval === currentThroughputInterval);
  });
}

function hideThroughputTooltip() {
  throughputTooltip.hidden = true;
  throughputTooltip.innerHTML = "";
}

function positionChartTooltip(container, tooltip, event) {
  const containerRect = container.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  const offsetX = event.clientX - containerRect.left + 14;
  const offsetY = event.clientY - containerRect.top - tooltipRect.height - 14;
  const left = Math.min(Math.max(offsetX, 8), Math.max(containerRect.width - tooltipRect.width - 8, 8));
  const top = offsetY < 8
    ? Math.min(event.clientY - containerRect.top + 14, Math.max(containerRect.height - tooltipRect.height - 8, 8))
    : offsetY;
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function utcDateForValue(value) {
  const date = new Date(value);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function isoWeekInfo(value) {
  const date = utcDateForValue(value);
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const isoYear = date.getUTCFullYear();
  const yearStart = new Date(Date.UTC(isoYear, 0, 1));
  const week = Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  const weekStart = new Date(date);
  weekStart.setUTCDate(date.getUTCDate() - 3);
  return {
    key: `${isoYear}-W${padNumber(week)}`,
    label: `W${padNumber(week)}`,
    fullLabel: `${isoYear}-W${padNumber(week)} (${weekStart.toISOString().slice(0, 10)})`,
    sortValue: weekStart.getTime(),
  };
}

function monthInfo(value) {
  const date = utcDateForValue(value);
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth() + 1;
  return {
    key: `${year}-${padNumber(month)}`,
    label: `${padNumber(month)}.${String(year).slice(-2)}`,
    fullLabel: `${year}-${padNumber(month)}`,
    sortValue: Date.UTC(year, month - 1, 1),
  };
}

function throughputBucketInfo(event, interval) {
  const completedAt = event?.completedAt;
  if (!completedAt) {
    return null;
  }
  return interval === "week" ? isoWeekInfo(completedAt) : monthInfo(completedAt);
}

function setActiveTab(tabName) {
  activeTab = tabName;
  tabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tabButton === tabName);
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.tabPanel === tabName);
  });
}

function isoDate(value) {
  return String(value || "").slice(0, 10);
}

function configDashboardDateDefaults() {
  const config = configsById[currentConfigId] || {};
  const formStart = String(form?.elements?.sync_start_date?.value || "").trim();
  const formEnd = String(form?.elements?.sync_end_date?.value || "").trim();
  return {
    start: String(config.sync_start_date || formStart || "").trim(),
    end: String(config.sync_end_date || formEnd || "").trim(),
  };
}

function parseIsoCalendarDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() + 1 !== month ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return { year, month, day };
}

function startOfDayMs(value) {
  return new Date(`${value}T00:00:00`).getTime();
}

function endOfDayMs(value) {
  return new Date(`${value}T23:59:59.999`).getTime();
}

function formatMonthDay(ms) {
  const date = new Date(ms);
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function quantileIndex(length, ratio) {
  if (length <= 1) {
    return 0;
  }
  return Math.min(length - 1, Math.max(0, Math.floor((length - 1) * ratio)));
}

function formPayload() {
  const data = new FormData(form);
  const projectKeys = selectedProjectKeys(data.get("project_keys"));
  const issueTypes = parseCsv(String(data.get("issue_types") || ""));
  const syncStartDate = String(data.get("sync_start_date") || "");
  const syncEndDate = String(data.get("sync_end_date") || "");
  const generatedBaseJql = buildGeneratedBaseJql({
    project_keys: projectKeys,
    issue_types: issueTypes,
    sync_start_date: syncStartDate,
    sync_end_date: syncEndDate,
  });
  const scopeType = generatedBaseJql ? "builder" : "jql";
  return {
    name: data.get("name"),
    jira_base_url: data.get("jira_base_url"),
    auth_type: "bearer_pat",
    verify_ssl: false,
    user_email: null,
    secret: data.get("secret"),
    scope_type: scopeType,
    board_id: null,
    project_keys: projectKeys,
    issue_types: issueTypes,
    base_jql: generatedBaseJql || data.get("base_jql"),
    extra_jql: data.get("extra_jql"),
    date_range_days: Number(data.get("date_range_days") || 90),
    sync_start_date: syncStartDate || null,
    sync_end_date: syncEndDate || null,
    start_status_ids: parseCsv(String(data.get("start_status_ids") || "")),
    done_status_ids: parseCsv(String(data.get("done_status_ids") || "")),
    active_status_ids: parseCsv(String(data.get("active_status_ids") || "")),
    attribution_mode: data.get("attribution_mode"),
    board_mapping: currentBoardMapping,
  };
}

function renderProjectOptions(projects) {
  availableProjects = projects || [];
  const currentValue = String(form.elements.project_keys.value || "").trim();
  const options = ['<option value="">Select visible Jira project</option>'];
  if (currentValue && !availableProjects.some((project) => project.key === currentValue)) {
    options.push(`<option value="${escapeHtml(currentValue)}">${escapeHtml(currentValue)}</option>`);
  }
  options.push(
    ...availableProjects.map(
      (project) =>
        `<option value="${escapeHtml(project.key)}">${escapeHtml(project.key)}${project.name ? ` - ${escapeHtml(project.name)}` : ""}</option>`
    )
  );
  projectSelect.innerHTML = options.join("");
  if (currentValue) {
    projectSelect.value = currentValue;
  }
}

async function loadProjects() {
  const payload = formPayload();
  if (!payload.jira_base_url || !payload.secret) {
    renderProjectOptions([]);
    return [];
  }
  const result = await request("/api/jira/projects", {
    method: "POST",
    body: JSON.stringify({
      baseUrl: payload.jira_base_url,
      secret: payload.secret,
      configId: currentConfigId,
    }),
  });
  renderProjectOptions(result.projects || []);
  return result.projects || [];
}

function buildGeneratedBaseJql(payload) {
  const clauses = [
    listClause("project", payload.project_keys || []),
    listClause("issuetype", payload.issue_types || []),
  ].filter(Boolean);

  if (payload.sync_start_date) {
    clauses.push(`updated >= "${payload.sync_start_date}"`);
  }
  if (payload.sync_end_date) {
    clauses.push(`updated < "${addDaysToIsoDate(payload.sync_end_date, 1)}"`);
  }
  return clauses.join(" AND ");
}

function buildEffectiveJql(payload) {
  const baseJql = buildGeneratedBaseJql(payload) || String(payload.base_jql || "").trim();
  if (!baseJql) {
    return "";
  }
  if (String(payload.extra_jql || "").trim()) {
    return `(${baseJql}) AND (${String(payload.extra_jql).trim()})`;
  }
  return baseJql;
}

function refreshGeneratedJqlPreview() {
  const payload = formPayload();
  form.elements.base_jql.value = buildGeneratedBaseJql(payload) || String(form.elements.base_jql.value || "");
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function renderBoardMapping(mapping) {
  if (!mapping || !Object.keys(statusCatalog).length) {
    mappingPreview.innerHTML = '<p class="metric-detail">Statuses from the selected Jira project and issue types will appear here after loading them from Jira.</p>';
    return;
  }
  const entries = statusEntriesFromBuckets();
  const buckets = [
    { id: "inactive", title: "Inactive statuses", items: entries.inactive },
    { id: "active", title: "Active statuses", items: entries.active },
    { id: "done", title: "Done statuses", items: entries.done },
  ];
  mappingPreview.innerHTML = `
    <div class="status-dnd-intro">
      Drag statuses between the three sections to decide how analytics should classify them.
    </div>
    <div class="status-bucket-grid">
      ${buckets.map((bucket) => `
        <section class="status-bucket" data-status-bucket="${bucket.id}">
          <div class="status-bucket-header">
            <strong>${bucket.title}</strong>
            <span>${bucket.items.length}</span>
          </div>
          <div class="status-bucket-list" data-status-dropzone="${bucket.id}">
            ${bucket.items.length ? bucket.items.map((status) => `
              <article class="status-chip" draggable="true" data-status-id="${escapeHtml(status.id)}">
                <strong>${escapeHtml(status.name)}</strong>
                <span>${escapeHtml(status.id)}</span>
              </article>
            `).join("") : '<p class="metric-detail">Drop statuses here.</p>'}
          </div>
        </section>
      `).join("")}
    </div>
  `;

  mappingPreview.querySelectorAll("[data-status-dropzone]").forEach((node) => {
    node.addEventListener("dragover", (event) => {
      event.preventDefault();
      node.classList.add("is-drag-over");
    });
    node.addEventListener("dragleave", () => {
      node.classList.remove("is-drag-over");
    });
    node.addEventListener("drop", (event) => {
      event.preventDefault();
      node.classList.remove("is-drag-over");
      const targetBucket = node.dataset.statusDropzone;
      const statusId = event.dataTransfer?.getData("text/plain") || draggedStatusId;
      if (statusId && targetBucket) {
        moveStatusToBucket(statusId, targetBucket);
      }
    });
  });

  mappingPreview.querySelectorAll("[data-status-id]").forEach((node) => {
    node.addEventListener("dragstart", (event) => {
      draggedStatusId = node.dataset.statusId;
      event.dataTransfer?.setData("text/plain", draggedStatusId);
      event.dataTransfer.effectAllowed = "move";
    });
    node.addEventListener("dragend", () => {
      draggedStatusId = null;
      mappingPreview.querySelectorAll(".is-drag-over").forEach((dropzone) => {
        dropzone.classList.remove("is-drag-over");
      });
    });
  });
}

function resetFormToDefaults() {
  form.reset();
  form.elements.secret.value = "";
  form.elements.start_status_ids.value = "";
  form.elements.done_status_ids.value = "";
  form.elements.active_status_ids.value = "";
  currentBoardMapping = null;
  statusCatalog = {};
  setStatusBuckets({ inactive: [], active: [], done: [] });
  renderBoardMapping(null);
  renderProjectOptions([]);
  refreshGeneratedJqlPreview();
}

function startNewConfiguration() {
  currentConfigId = null;
  resetFormToDefaults();
  renderConfigs(Object.values(configsById));
  setSyncStatus("idle", {
    progress: 0,
    message: "This is a new unsaved configuration. Save draft or run sync to create it.",
    help: "Fill in the wizard fields, then save or sync to create a separate config.",
  });
  setActiveTab("configuration");
  writeStatus("Creating a new configuration.", {
    mode: "new",
    detail: "The wizard was reset. Saving now will create a new config instead of updating the selected one.",
  });
}

function hydrateForm(config) {
  if (!config) {
    return;
  }
  form.elements.name.value = config.name || "";
  form.elements.jira_base_url.value = config.jira_base_url || "";
  form.elements.secret.value = config.secret || "";
  form.elements.project_keys.value = (config.project_keys || []).join(", ");
  form.elements.issue_types.value = (config.issue_types || []).join(", ");
  form.elements.sync_start_date.value = config.sync_start_date || "";
  form.elements.sync_end_date.value = config.sync_end_date || "";
  form.elements.base_jql.value = config.base_jql || "";
  form.elements.extra_jql.value = config.extra_jql || "";
  form.elements.date_range_days.value = config.date_range_days || 90;
  form.elements.attribution_mode.value = config.attribution_mode || "assignee_at_done";
  currentBoardMapping = config.board_mapping || null;
  initializeStatusBucketsFromConfig(config);
  renderBoardMapping(currentBoardMapping);
  refreshGeneratedJqlPreview();
}

async function persistConfig() {
  const payload = formPayload();
  const method = currentConfigId ? "PUT" : "POST";
  const url = currentConfigId ? `/api/configs/${currentConfigId}` : "/api/configs";
  const result = await request(url, {
    method,
    body: JSON.stringify(payload),
  });
  currentConfigId = result.config.id;
  configsById[currentConfigId] = result.config;
  await refreshConfigs();
  return result.config;
}

async function saveConfig(event) {
  event.preventDefault();
  const config = await persistConfig();
  writeStatus("Configuration saved locally.", config);
}

async function testConnection() {
  const payload = formPayload();
  const result = await request("/api/jira/test-connection", {
    method: "POST",
    body: JSON.stringify({
      baseUrl: payload.jira_base_url,
      secret: payload.secret,
      configId: currentConfigId,
    }),
  });
  try {
    const projects = await loadProjects();
    writeStatus("Jira connection succeeded.", { ...result, projectsLoaded: projects.length });
  } catch (error) {
    writeStatus("Jira connection succeeded, but project list failed to load.", {
      ...result,
      projectLoadError: error.message,
    });
  }
}

async function validateJql() {
  const payload = formPayload();
  const jql = buildEffectiveJql(payload);
  if (!jql) {
    writeStatus("Enter at least one project, issue type, date filter, or legacy base JQL before validation.");
    return;
  }
  const result = await request("/api/jira/validate-jql", {
    method: "POST",
    body: JSON.stringify({
      baseUrl: payload.jira_base_url,
      secret: payload.secret,
      jql,
      configId: currentConfigId,
    }),
  });
  if (result.cleanedJql && result.cleanedJql !== jql) {
    form.elements.base_jql.value = result.cleanedJql;
  }
  writeStatus("JQL validation succeeded.", result);
}

async function loadProjectStatuses() {
  const payload = formPayload();
  const projectKey = (payload.project_keys || [])[0] || "";
  if (!projectKey) {
    writeStatus("Choose a Project key before loading statuses.");
    return;
  }
  const result = await request("/api/jira/project-statuses", {
    method: "POST",
    body: JSON.stringify({
      baseUrl: payload.jira_base_url,
      secret: payload.secret,
      configId: currentConfigId,
      projectKey,
      issueTypes: payload.issue_types || [],
    }),
  });
  currentBoardMapping = result.mapping;
  const allStatuses = uniqueStatusEntries(
    (result.statuses || []).map((status) => ({ id: String(status.id), name: status.name || String(status.id) }))
  );
  statusCatalog = Object.fromEntries(allStatuses.map((status) => [status.id, status]));
  const activeIds = result.activeStatusIds || [];
  const doneIds = result.doneStatusIds || [];
  const inactiveIds = allStatuses
    .map((status) => status.id)
    .filter((statusId) => !activeIds.includes(statusId) && !doneIds.includes(statusId));
  setStatusBuckets({
    inactive: inactiveIds,
    active: activeIds,
    done: doneIds,
  });
  renderBoardMapping(currentBoardMapping);
  writeStatus("Workflow statuses loaded for the selected project and issue types.", result);
}

async function loadDemo() {
  const result = await request("/api/demo/bootstrap", {
    method: "POST",
    body: JSON.stringify({}),
  });
  currentConfigId = result.config.id;
  configsById[currentConfigId] = result.config;
  hydrateForm(result.config);
  loadProjects().catch(() => undefined);
  writeStatus("Demo data loaded locally.", result.config);
  await refreshConfigs();
  await loadMetrics(currentConfigId);
}

async function refreshConfigs() {
  const result = await request("/api/configs");
  const configs = result.configs || [];
  configsById = Object.fromEntries(configs.map((config) => [config.id, config]));
  if (currentConfigId && !configsById[currentConfigId]) {
    currentConfigId = null;
  }
  renderConfigs(configs);
  if (currentConfigId && configsById[currentConfigId]) {
    return;
  }
  resetFormToDefaults();
  setDashboardEmptyState(
    configs.length
      ? {
          title: "Choose a saved config to view metrics.",
          detail: "Pick any config card above to load its charts and filters.",
        }
      : {
          title: "No saved configs yet.",
          detail: "Open the wizard to create a config, or load the demo dataset to see the dashboard.",
        }
  );
}

function renderConfigs(configs) {
  if (!configs.length) {
    configList.innerHTML = '<div class="config-item">No saved configs yet.</div>';
    return;
  }
  configList.innerHTML = configs
    .map(
      (config) => `
        <div class="config-card">
          <button class="config-item ${config.id === currentConfigId ? "is-selected" : ""}" data-config-id="${config.id}" type="button">
            <strong>${escapeHtml(config.name)}</strong>
            <div>${escapeHtml((config.project_keys || []).join(", ") || config.scope_type.toUpperCase())} · ${escapeHtml((config.issue_types || []).join(", ") || (config.jira_base_url || "No filters yet"))}</div>
          </button>
          <button
            class="config-delete-button"
            data-delete-config-id="${config.id}"
            type="button"
            aria-label="Delete ${escapeHtml(config.name)}"
            title="Delete config"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm-1 5h8v10a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V8zm1 2v7h2v-7H9zm4 0v7h2v-7h-2z" fill="currentColor"></path>
            </svg>
          </button>
        </div>
      `
    )
    .join("");

  document.querySelectorAll("[data-config-id]").forEach((node) => {
    node.addEventListener("click", async () => {
      currentConfigId = node.getAttribute("data-config-id");
      hydrateForm(configsById[currentConfigId]);
      renderConfigs(Object.values(configsById));
      loadProjects().catch(() => undefined);
      await loadMetrics(currentConfigId);
    });
  });

  document.querySelectorAll("[data-delete-config-id]").forEach((node) => {
    node.addEventListener("click", async () => {
      const configId = node.getAttribute("data-delete-config-id");
      if (configId) {
        await deleteConfig(configId);
      }
    });
  });
}

async function deleteConfig(configId) {
  const config = configsById[configId];
  if (!config) {
    return;
  }
  const confirmed = window.confirm(
    `Delete config "${config.name}"?\n\nThis will remove its synced issues and job history from the local dashboard.`
  );
  if (!confirmed) {
    return;
  }
  await request(`/api/configs/${encodeURIComponent(configId)}`, { method: "DELETE" });
  if (currentConfigId === configId) {
    currentConfigId = null;
  }
  writeStatus("Configuration deleted.", { configId, name: config.name });
  await refreshConfigs();
}

async function runSync() {
  setSyncStatus("running", {
    progress: 0.02,
    message: "Saving the current configuration before sync starts.",
  });
  try {
    const savedConfig = await persistConfig();
    const result = await request(`/api/configs/${currentConfigId}/sync`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    activeSyncJobId = result.job.id;
    setSyncStatus(result.job.status, {
      progress: result.job.progress,
      message: result.job.message,
      help: "The app is now loading issues and changelog history from Jira.",
    });
    writeStatus("Step 4 started: syncing issues from Jira.", {
      configId: savedConfig.id,
      job: result.job,
    });
    pollJob(result.job.id).catch((error) => {
      setSyncStatus("failed", {
        progress: 0,
        message: error.message,
        suggestions: syncFailureSuggestions(error.message),
      });
      writeStatus("Sync polling failed.", { error: error.message, jobId: result.job.id });
    });
  } catch (error) {
    setSyncStatus("failed", {
      progress: 0,
      message: error.message,
      suggestions: syncFailureSuggestions(error.message),
    });
    throw error;
  }
}

async function pollJob(jobId) {
  let done = false;
  while (!done) {
    const result = await request(`/api/jobs/${jobId}`);
    writeStatus("Sync job update.", result.job);
    setSyncStatus(result.job.status, {
      progress: result.job.progress,
      message: result.job.message,
      suggestions: result.job.status === "failed" ? syncFailureSuggestions(result.job.message) : [],
    });
    done = ["completed", "failed"].includes(result.job.status);
    if (!done) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
    } else if (result.job.status === "completed") {
      activeSyncJobId = null;
      await loadMetrics(currentConfigId);
    } else {
      activeSyncJobId = null;
    }
  }
}

function renderLineChart(containerId, values, valueAccessor, labelAccessor, color = "var(--accent)") {
  const container = document.getElementById(containerId);
  if (!values || !values.length) {
    container.innerHTML = '<p class="metric-detail">No trend data yet.</p>';
    return;
  }

  const width = 620;
  const height = 180;
  const padding = 24;
  const maxValue = Math.max(...values.map(valueAccessor), 1);
  const stepX = values.length === 1 ? 0 : (width - padding * 2) / (values.length - 1);

  const points = values.map((item, index) => {
    const x = padding + stepX * index;
    const y = height - padding - (valueAccessor(item) / maxValue) * (height - padding * 2);
    return [x, y];
  });

  const line = points.map(([x, y]) => `${x},${y}`).join(" ");
  const area = `M ${padding},${height - padding} L ${points.map(([x, y]) => `${x},${y}`).join(" L ")} L ${width - padding},${height - padding} Z`;
  const labels = values
    .map((item, index) => {
      const [x] = points[index];
      return `<text class="chart-label" x="${x}" y="${height - 6}" text-anchor="middle">${labelAccessor(item)}</text>`;
    })
    .join("");

  container.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      <line class="chart-grid-line" x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"></line>
      <path class="chart-area" d="${area}"></path>
      <polyline class="chart-line" points="${line}" style="stroke:${color}"></polyline>
      ${labels}
    </svg>
  `;
}

function renderBarChart(containerId, values, valueAccessor, labelAccessor, options = {}) {
  const container = document.getElementById(containerId);
  if (!values || !values.length) {
    container.innerHTML = `<p class="metric-detail">${escapeHtml(options.emptyMessage || "No distribution data yet.")}</p>`;
    return;
  }

  const width = 620;
  const height = 220;
  const paddingLeft = 54;
  const paddingRight = 16;
  const paddingTop = 18;
  const paddingBottom = 44;
  const maxValue = Math.max(...values.map(valueAccessor), 1);
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;
  const gap = Math.min(12, Math.max(4, chartWidth * 0.04 / Math.max(values.length, 1)));
  const barWidth = Math.max((chartWidth - gap * (values.length - 1)) / values.length, 8);
  const labelStep = Math.max(1, Math.ceil(values.length / 8));
  const tickStep = Math.max(1, Math.ceil(maxValue / 4));
  const yTicks = [];
  for (let value = 0; value <= maxValue; value += tickStep) {
    yTicks.push(value);
  }
  if (yTicks.at(-1) !== maxValue) {
    yTicks.push(maxValue);
  }

  const bars = values
    .map((item, index) => {
      const value = valueAccessor(item);
      const x = paddingLeft + index * (barWidth + gap);
      const barHeight = (value / maxValue) * chartHeight;
      const y = height - paddingBottom - barHeight;
      const shouldRenderLabel = index % labelStep === 0 || index === values.length - 1;
      return `
        <rect class="chart-bar" data-bar-index="${index}" x="${x}" y="${y}" width="${barWidth}" height="${barHeight}"></rect>
        ${shouldRenderLabel ? `<text class="chart-label" x="${x + barWidth / 2}" y="${height - 18}" text-anchor="middle">${escapeHtml(labelAccessor(item))}</text>` : ""}
      `;
    })
    .join("");

  const yGrid = yTicks
    .map((value) => {
      const y = height - paddingBottom - (value / maxValue) * chartHeight;
      return `
        <line class="chart-grid-line" x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}"></line>
        <text class="chart-axis-label" x="${paddingLeft - 8}" y="${y + 4}" text-anchor="end">${escapeHtml(String(value))}</text>
      `;
    })
    .join("");

  container.innerHTML = `
    <svg class="chart-svg${options.svgClass ? ` ${escapeHtml(options.svgClass)}` : ""}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      ${yGrid}
      <line class="chart-grid-line" x1="${paddingLeft}" y1="${height - paddingBottom}" x2="${width - paddingRight}" y2="${height - paddingBottom}"></line>
      <text class="chart-axis-title" x="${paddingLeft - 36}" y="${paddingTop + chartHeight / 2}" text-anchor="middle" transform="rotate(-90 ${paddingLeft - 36} ${paddingTop + chartHeight / 2})">${escapeHtml(options.yAxisTitle || "Value")}</text>
      <text class="chart-axis-title" x="${paddingLeft + chartWidth / 2}" y="${height - 2}" text-anchor="middle">${escapeHtml(options.xAxisTitle || "Buckets")}</text>
      ${bars}
    </svg>
  `;

  if (typeof options.tooltipHtml !== "function") {
    return;
  }

  const tooltip = throughputTooltip;
  if (tooltip.parentElement !== container) {
    container.appendChild(tooltip);
  }
  const barElements = Array.from(container.querySelectorAll("[data-bar-index]"));
  barElements.forEach((bar) => {
    const item = values[Number(bar.dataset.barIndex)];
    const showTooltip = (event) => {
      tooltip.innerHTML = options.tooltipHtml(item);
      tooltip.hidden = false;
      positionChartTooltip(container, tooltip, event);
    };
    bar.addEventListener("mouseenter", showTooltip);
    bar.addEventListener("mousemove", showTooltip);
    bar.addEventListener("mouseleave", () => {
      hideThroughputTooltip();
    });
  });
}

function cfdSeriesNames(data) {
  const fromSeries = (data?.series || []).map((item) => item.name).filter(Boolean);
  if (fromSeries.length) {
    return fromSeries;
  }
  const fromMeta = data?.meta?.seriesOrder || [];
  if (fromMeta.length) {
    return fromMeta;
  }
  return Object.keys(data?.points?.[0]?.current || {});
}

function cfdStackOrder(data) {
  const stackOrder = data?.meta?.stackingOrder || [];
  if (stackOrder.length) {
    return stackOrder;
  }
  return [...cfdSeriesNames(data)].reverse();
}

function cfdColorForSeries(index, total) {
  const palette = ["#0d6c63", "#3f8b76", "#7ea05b", "#c8893c", "#d7a55a", "#cf6b4f"];
  if (total <= palette.length) {
    return palette[index];
  }
  const hue = interpolateValue(168, 14, total <= 1 ? 0 : index / (total - 1));
  const saturation = interpolateValue(62, 68, total <= 1 ? 0 : index / (total - 1));
  const lightness = interpolateValue(31, 55, total <= 1 ? 0 : index / (total - 1));
  return `hsl(${hue.toFixed(0)} ${saturation.toFixed(0)}% ${lightness.toFixed(0)}%)`;
}

function renderCfdLegend(names) {
  if (!names.length) {
    cfdLegend.innerHTML = "";
    return;
  }
  cfdLegend.innerHTML = names
    .map((name, index) => `
      <button class="chart-legend-pill" type="button" data-cfd-series-name="${escapeHtml(name)}">
        <span class="chart-legend-swatch" style="background:${escapeHtml(cfdColorForSeries(index, names.length))}"></span>
        <span>${escapeHtml(name)}</span>
      </button>
    `)
    .join("");
}

function hideCfdContextMenu() {
  cfdContextSeriesName = null;
  cfdContextMenu.hidden = true;
}

function showCfdContextMenu(target, event) {
  cfdContextSeriesName = target.dataset.cfdSeriesName || null;
  if (!cfdContextSeriesName) {
    hideCfdContextMenu();
    return;
  }

  if (cfdContextMenu.parentElement !== cfdLegend) {
    cfdLegend.appendChild(cfdContextMenu);
  }

  cfdContextMenu.hidden = false;
  const shellRect = cfdLegend.getBoundingClientRect();
  const menuRect = cfdContextMenu.getBoundingClientRect();
  const offsetX = event.clientX - shellRect.left + 10;
  const offsetY = event.clientY - shellRect.top + 10;
  const left = Math.min(Math.max(offsetX, 8), Math.max(shellRect.width - menuRect.width - 8, 8));
  const top = Math.min(Math.max(offsetY, 8), Math.max(shellRect.height - menuRect.height - 8, 8));
  cfdContextMenu.style.left = `${left}px`;
  cfdContextMenu.style.top = `${top}px`;
}

function updateCfdHiddenControls(allSeriesNames = []) {
  const hiddenNames = [...hiddenCfdSeriesForCurrentConfig()].filter((name) => !allSeriesNames.length || allSeriesNames.includes(name));
  cfdHiddenControls.hidden = hiddenNames.length === 0;
  cfdHiddenCount.textContent = `${hiddenNames.length} status${hiddenNames.length === 1 ? "" : "es"} hidden`;
}

function renderStackedAreaChart(containerId, points, seriesNames, options = {}) {
  const container = document.getElementById(containerId);
  if (!points || !points.length || !seriesNames.length) {
    container.innerHTML = `<p class="metric-detail">${escapeHtml(options.emptyMessage || "No CFD data yet.")}</p>`;
    return;
  }

  const width = 620;
  const height = 260;
  const paddingLeft = 54;
  const paddingRight = 18;
  const paddingTop = 18;
  const paddingBottom = 44;
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;
  const xCoordinates = points.map((_, index) => (
    points.length === 1
      ? paddingLeft + chartWidth / 2
      : paddingLeft + (chartWidth * index) / (points.length - 1)
  ));
  const totals = points.map((point) => seriesNames.reduce((sum, name) => sum + (point.current?.[name] || 0), 0));
  const maxTotal = Math.max(...totals, 1);
  const yForValue = (value) => height - paddingBottom - (value / maxTotal) * chartHeight;
  const tickStep = Math.max(1, Math.ceil(maxTotal / 4));
  const yTicks = [];
  for (let value = 0; value <= maxTotal; value += tickStep) {
    yTicks.push(value);
  }
  if (yTicks.at(-1) !== maxTotal) {
    yTicks.push(maxTotal);
  }
  const labelStep = Math.max(1, Math.ceil(points.length / 8));
  const xLabels = points
    .map((point, index) => {
      if (index % labelStep !== 0 && index !== points.length - 1) {
        return "";
      }
      return `<text class="chart-label" x="${xCoordinates[index]}" y="${height - 18}" text-anchor="middle">${escapeHtml(point.day.slice(5))}</text>`;
    })
    .join("");
  const yGrid = yTicks
    .map((value) => {
      const y = yForValue(value);
      return `
        <line class="chart-grid-line" x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}"></line>
        <text class="chart-axis-label" x="${paddingLeft - 8}" y="${y + 4}" text-anchor="end">${escapeHtml(String(value))}</text>
      `;
    })
    .join("");

  const bands = [];
  let lowerValues = Array(points.length).fill(0);
  seriesNames.forEach((name, index) => {
    const bandValues = points.map((point) => point.current?.[name] || 0);
    const upperValues = bandValues.map((value, valueIndex) => lowerValues[valueIndex] + value);
    const topPolyline = xCoordinates.map((x, valueIndex) => `${x},${yForValue(upperValues[valueIndex])}`).join(" ");
    const bottomPolyline = xCoordinates
      .map((x, valueIndex) => `${x},${yForValue(lowerValues[valueIndex])}`)
      .reverse()
      .join(" ");
    const color = cfdColorForSeries(index, seriesNames.length);
    bands.push(`
      <path class="chart-stack-band" d="M ${topPolyline.replaceAll(' ', ' L ')} L ${bottomPolyline.replaceAll(' ', ' L ')} Z" fill="${color}"></path>
      <polyline class="chart-stack-boundary" points="${topPolyline}" style="stroke:${color}"></polyline>
    `);
    lowerValues = upperValues;
  });

  container.innerHTML = `
    <svg class="chart-svg chart-svg-large" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      ${yGrid}
      <line class="chart-grid-line" x1="${paddingLeft}" y1="${height - paddingBottom}" x2="${width - paddingRight}" y2="${height - paddingBottom}"></line>
      <text class="chart-axis-title" x="${paddingLeft - 36}" y="${paddingTop + chartHeight / 2}" text-anchor="middle" transform="rotate(-90 ${paddingLeft - 36} ${paddingTop + chartHeight / 2})">Tasks</text>
      <text class="chart-axis-title" x="${paddingLeft + chartWidth / 2}" y="${height - 2}" text-anchor="middle">Calendar day</text>
      ${bands.join("")}
      ${xLabels}
    </svg>
  `;
}

function renderScatterChart(containerId, values, options = {}) {
  const container = document.getElementById(containerId);
  if (!values || !values.length) {
    container.innerHTML = '<p class="metric-detail">No cycle time data yet.</p>';
    return;
  }

  const sorted = [...values].sort((left, right) => new Date(left.end).getTime() - new Date(right.end).getTime());
  const width = 620;
  const height = 220;
  const paddingLeft = 62;
  const paddingRight = 20;
  const paddingTop = 16;
  const paddingBottom = 42;
  const minX = options.minX ?? new Date(sorted[0].end).getTime();
  const maxX = options.maxX ?? new Date(sorted.at(-1).end).getTime();
  const maxY = Math.max(options.maxY ?? Math.max(...sorted.map((item) => item.hours), 1), 1);
  const xSpan = Math.max(maxX - minX, 1);
  const yTicks = [0, maxY * 0.33, maxY * 0.66, maxY];

  const circles = sorted
    .map((item) => {
      const x = paddingLeft + ((new Date(item.end).getTime() - minX) / xSpan) * (width - paddingLeft - paddingRight);
      const y = height - paddingBottom - (item.hours / maxY) * (height - paddingTop - paddingBottom);
      return `
        <circle
          class="chart-point"
          cx="${x}"
          cy="${y}"
          r="4.5"
          data-issue-key="${escapeHtml(item.issueKey)}"
          data-summary="${escapeHtml(item.summary || item.issueKey)}"
          data-done-date="${escapeHtml(item.end.slice(0, 10))}"
          data-cycle="${escapeHtml(formatDuration(item.hours))}"
        ></circle>
      `;
    })
    .join("");

  const yGrid = yTicks
    .map((value) => {
      const y = height - paddingBottom - (value / maxY) * (height - paddingTop - paddingBottom);
      return `
        <line class="chart-grid-line" x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}"></line>
        <text class="chart-axis-label" x="${paddingLeft - 8}" y="${y + 4}" text-anchor="end">${formatDuration(value)}</text>
      `;
    })
    .join("");

  const labelMs = [minX, minX + xSpan / 2, maxX];
  const xLabels = labelMs
    .map((value) => {
      const x = paddingLeft + ((value - minX) / xSpan) * (width - paddingLeft - paddingRight);
      return `<text class="chart-axis-label" x="${x}" y="${height - 18}" text-anchor="middle">${formatMonthDay(value)}</text>`;
    })
    .join("");

  container.innerHTML = `
    <svg class="chart-svg chart-svg-tall" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      ${yGrid}
      <line class="chart-grid-line" x1="${paddingLeft}" y1="${height - paddingBottom}" x2="${width - paddingRight}" y2="${height - paddingBottom}"></line>
      <line class="chart-grid-line" x1="${paddingLeft}" y1="${paddingTop}" x2="${paddingLeft}" y2="${height - paddingBottom}"></line>
      ${circles}
      ${xLabels}
      <text class="chart-axis-title" x="${width / 2}" y="${height - 4}" text-anchor="middle">Done date</text>
      <text class="chart-axis-title" x="18" y="${height / 2}" text-anchor="middle" transform="rotate(-90 18 ${height / 2})">Cycle time</text>
    </svg>
  `;
}

function hideCycleTooltip() {
  cycleTooltip.hidden = true;
  cycleTooltip.innerHTML = "";
}

function hideCycleContextMenu() {
  cycleContextIssueKey = null;
  cycleContextMenu.hidden = true;
}

function showCycleContextMenu(target, event) {
  cycleContextIssueKey = target.dataset.issueKey || null;
  if (!cycleContextIssueKey) {
    hideCycleContextMenu();
    return;
  }

  if (cycleContextMenu.parentElement !== cycleTrendChart) {
    cycleTrendChart.appendChild(cycleContextMenu);
  }

  cycleContextMenu.hidden = false;
  const shellRect = cycleTrendChart.getBoundingClientRect();
  const menuRect = cycleContextMenu.getBoundingClientRect();
  const offsetX = event.clientX - shellRect.left + 10;
  const offsetY = event.clientY - shellRect.top + 10;
  const left = Math.min(Math.max(offsetX, 8), Math.max(shellRect.width - menuRect.width - 8, 8));
  const top = Math.min(Math.max(offsetY, 8), Math.max(shellRect.height - menuRect.height - 8, 8));
  cycleContextMenu.style.left = `${left}px`;
  cycleContextMenu.style.top = `${top}px`;
}

function updateHiddenIssuesControls() {
  const hiddenCount = hiddenIssueCountForCurrentConfig();
  cycleHiddenControls.hidden = hiddenCount === 0;
  cycleHiddenCount.textContent = `${hiddenCount} task${hiddenCount === 1 ? "" : "s"} hidden`;
}

function dashboardEmptyMarkup(title, detail) {
  return `
    <div class="dashboard-empty-state">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(detail)}</p>
    </div>
  `;
}

function setCycleInputValidity(input, message = "") {
  input.setCustomValidity(message);
  input.classList.toggle("is-invalid", Boolean(message));
}

function clearCycleControlsError() {
  cycleControlsError.hidden = true;
  cycleControlsError.textContent = "";
}

function setDashboardEmptyState({ title, detail }) {
  currentCycleData = null;
  currentThroughputData = null;
  currentPhaseRatioData = null;
  currentCfdData = null;

  hideCycleTooltip();
  hideThroughputTooltip();
  hideCycleContextMenu();
  clearCycleControlsError();
  cycleHiddenControls.hidden = true;
  cycleHiddenCount.textContent = "0 tasks hidden";

  [cycleXStartInput, cycleXEndInput].forEach((input) => {
    input.value = "";
    input.min = "";
    input.max = "";
    input.disabled = true;
    input.dataset.absoluteMin = "";
    input.dataset.absoluteMax = "";
    input.dataset.suggestedStart = "";
    input.dataset.suggestedEnd = "";
    setCycleInputValidity(input);
  });
  cycleYMaxInput.value = "";
  cycleYMaxInput.min = "0.1";
  cycleYMaxInput.max = "";
  cycleYMaxInput.disabled = true;
  cycleYMaxInput.dataset.absoluteMax = "";
  cycleYMaxInput.dataset.suggestedMax = "";
  cycleFitP95Button.disabled = true;
  cycleShowAllButton.disabled = true;

  document.getElementById("cycle-detail").textContent = detail;
  cycleTrendChart.innerHTML = dashboardEmptyMarkup(title, detail);
  cyclePercentiles.innerHTML = `<p class="metric-detail">${escapeHtml(detail)}</p>`;
  document.getElementById("phase-status-detail").textContent = detail;
  document.getElementById("phase-status-summary").innerHTML = `<p class="metric-detail">${escapeHtml(detail)}</p>`;
  document.getElementById("throughput-summary").textContent = "No config selected";
  document.getElementById("throughput-detail").textContent = detail;
  document.getElementById("throughput-chart").innerHTML = dashboardEmptyMarkup(title, detail);
  document.getElementById("cfd-detail").textContent = detail;
  cfdLegend.innerHTML = "";
  cfdHiddenControls.hidden = true;
  cfdHiddenCount.textContent = "0 statuses hidden";
  hideCfdContextMenu();
  document.getElementById("cfd-chart").innerHTML = dashboardEmptyMarkup(title, detail);
}

function percentileValue(sortedValues, ratio) {
  if (!sortedValues.length) {
    return null;
  }
  if (sortedValues.length === 1) {
    return sortedValues[0];
  }
  const index = (sortedValues.length - 1) * ratio;
  const lower = Math.floor(index);
  const upper = Math.min(lower + 1, sortedValues.length - 1);
  const fraction = index - lower;
  return sortedValues[lower] + (sortedValues[upper] - sortedValues[lower]) * fraction;
}

function renderCyclePercentiles(issues) {
  if (!issues.length) {
    cyclePercentiles.innerHTML = '<p class="metric-detail">Percentiles will appear when the chart has visible issues.</p>';
    return;
  }

  const sortedHours = issues
    .map((item) => item.hours)
    .sort((left, right) => left - right);

  const values = [
    { label: "P50", value: percentileValue(sortedHours, 0.5) },
    { label: "P85", value: percentileValue(sortedHours, 0.85) },
    { label: "P95", value: percentileValue(sortedHours, 0.95) },
  ];

  cyclePercentiles.innerHTML = values
    .map(
      ({ label, value }) => `
        <div class="cycle-percentile">
          <p class="cycle-percentile-label">${label}</p>
          <p class="cycle-percentile-value">${escapeHtml(formatDuration(value || 0))}</p>
        </div>
      `
    )
    .join("");
}

function selectedDashboardDateRange(issues) {
  if (!issues.length) {
    return null;
  }

  const sorted = [...issues].sort((left, right) => new Date(left.end).getTime() - new Date(right.end).getTime());
  let xStart = cycleXStartInput.value || isoDate(sorted[0].end);
  let xEnd = cycleXEndInput.value || isoDate(sorted.at(-1).end);
  if (xStart > xEnd) {
    [xStart, xEnd] = [xEnd, xStart];
    cycleXStartInput.value = xStart;
    cycleXEndInput.value = xEnd;
  }

  return {
    xStart,
    xEnd,
    xStartMs: startOfDayMs(xStart),
    xEndMs: endOfDayMs(xEnd),
  };
}

function filterItemsByDateRange(items, valueAccessor, range) {
  if (!range) {
    return [...items];
  }
  return items.filter((item) => {
    const value = valueAccessor(item);
    if (!value) {
      return false;
    }
    const timestamp = typeof value === "number" ? value : new Date(value).getTime();
    return timestamp >= range.xStartMs && timestamp <= range.xEndMs;
  });
}

function parseIsoDayParts(value) {
  const [year, month, day] = String(value || "").split("-").map(Number);
  return { year, month, day };
}

function utcDayStartMs(value) {
  const { year, month, day } = parseIsoDayParts(value);
  return Date.UTC(year, month - 1, day, 0, 0, 0, 0);
}

function utcDayEndMs(value) {
  const { year, month, day } = parseIsoDayParts(value);
  return Date.UTC(year, month - 1, day, 23, 59, 59, 999);
}

function nextIsoDay(value) {
  const { year, month, day } = parseIsoDayParts(value);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
}

function buildIssueStatusIntervals(issue, reportEndMs) {
  const transitions = [...(issue.transitions || [])]
    .map((transition) => ({
      timestampMs: new Date(transition.timestamp).getTime(),
      toStatusId: transition.toStatusId,
    }))
    .sort((left, right) => left.timestampMs - right.timestampMs);

  const intervals = [];
  let currentStatusId = issue.initialStatusId;
  let currentStartMs = new Date(issue.createdAt).getTime();

  transitions.forEach((transition) => {
    if (transition.timestampMs < currentStartMs) {
      return;
    }
    if (transition.timestampMs > currentStartMs) {
      intervals.push({
        startMs: currentStartMs,
        endMs: transition.timestampMs,
        statusId: currentStatusId,
      });
    }
    currentStatusId = transition.toStatusId;
    currentStartMs = transition.timestampMs;
  });

  const finalStatusId = issue.currentStatusId || currentStatusId;
  if (reportEndMs > currentStartMs) {
    intervals.push({
      startMs: currentStartMs,
      endMs: reportEndMs,
      statusId: finalStatusId,
    });
  }

  return intervals;
}

function statusAtInstant(intervals, instantMs) {
  for (const interval of intervals) {
    if (interval.startMs <= instantMs && instantMs < interval.endMs) {
      return interval.statusId;
    }
  }
  if (intervals.length && instantMs >= intervals.at(-1).endMs) {
    return intervals.at(-1).statusId;
  }
  return null;
}

function recomputeCfdPoints(data) {
  const mapping = configsById[currentConfigId]?.board_mapping || currentBoardMapping;
  const sourceIssues = visibleCycleIssues(data?.issues || []);
  if (!mapping?.columns?.length || !sourceIssues.length || !(data?.points || []).length) {
    return [];
  }

  const phaseNames = mapping.columns.map((column) => column.name);
  const statusToColumn = Object.fromEntries(
    mapping.columns.flatMap((column) => (column.status_ids || []).map((statusId) => [statusId, column]))
  );
  const startDay = data.points[0].day;
  const endDay = data.points.at(-1).day;
  const perIssueIntervals = Object.fromEntries(
    sourceIssues.map((issue) => [
      issue.issueKey,
      buildIssueStatusIntervals(issue, utcDayStartMs(nextIsoDay(endDay))),
    ])
  );

  const points = [];
  for (let day = startDay; day <= endDay; day = nextIsoDay(day)) {
    const instantMs = utcDayEndMs(day);
    const current = Object.fromEntries(phaseNames.map((name) => [name, 0]));
    const cumulative = Object.fromEntries(phaseNames.map((name) => [name, 0]));

    Object.values(perIssueIntervals).forEach((intervals) => {
      const statusId = statusAtInstant(intervals, instantMs);
      if (!statusId) {
        return;
      }
      const column = statusToColumn[statusId];
      if (!column) {
        return;
      }
      const index = mapping.columns.findIndex((item) => item.id === column.id);
      current[column.name] += 1;
      for (let cumulativeIndex = 0; cumulativeIndex <= index; cumulativeIndex += 1) {
        cumulative[mapping.columns[cumulativeIndex].name] += 1;
      }
    });

    points.push({
      day,
      current,
      cumulative,
      wipTotal: Object.values(current).reduce((sum, value) => sum + value, 0),
    });
  }

  return points;
}

function bucketizeValues(values, bucketCount = 6) {
  if (!values.length) {
    return [];
  }
  const low = Math.min(...values);
  const high = Math.max(...values);
  if (low === high) {
    return [{ min: low, max: high, count: values.length, label: `${Math.round(low / 3600)}h` }];
  }

  const step = Math.max((high - low) / bucketCount, 1);
  return Array.from({ length: bucketCount }, (_, index) => {
    const bucketMin = low + index * step;
    const bucketMax = index === bucketCount - 1 ? high : low + (index + 1) * step;
    const count = values.filter((value) => (
      index === bucketCount - 1
        ? value >= bucketMin && value <= bucketMax
        : value >= bucketMin && value < bucketMax
    )).length;
    return {
      min: bucketMin,
      max: bucketMax,
      count,
      label: `${Math.round(bucketMin / 3600)}-${Math.round(bucketMax / 3600)}h`,
    };
  });
}

function selectedCycleIssuesInDateRange() {
  const issues = visibleCycleIssues(currentCycleData?.issues || []);
  const range = selectedDashboardDateRange(issues);
  return filterItemsByDateRange(issues, (item) => item.end, range);
}

function aggregateThroughputData(events, interval) {
  const buckets = {};

  events.forEach((event) => {
    const bucket = throughputBucketInfo(event, interval);
    if (!bucket) {
      return;
    }
    if (!buckets[bucket.key]) {
      buckets[bucket.key] = {
        key: bucket.key,
        label: bucket.label,
        fullLabel: bucket.fullLabel,
        sortValue: bucket.sortValue,
        count: 0,
        byAssignee: {},
      };
    }

    const assignee = event.assignee || event.owner || "unassigned";
    buckets[bucket.key].count += 1;
    buckets[bucket.key].byAssignee[assignee] = (buckets[bucket.key].byAssignee[assignee] || 0) + 1;
  });

  return Object.values(buckets)
    .sort((left, right) => left.sortValue - right.sortValue)
    .map((bucket) => ({
      ...bucket,
      byAssignee: Object.fromEntries(
        Object.entries(bucket.byAssignee).sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
      ),
    }));
}

function uniqueValues(values) {
  return [...new Set(values)];
}

function clampValue(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function interpolateValue(start, end, ratio) {
  return start + (end - start) * ratio;
}

function cycleStatusDescriptors() {
  const config = configsById[currentConfigId] || {};
  const mapping = config.board_mapping || currentBoardMapping;
  const statusNames = mapping?.status_names || {};
  const startStatusIds = new Set(config.start_status_ids || parseCsv(String(form.elements.start_status_ids.value || "")));
  const doneStatusIds = new Set(config.done_status_ids || parseCsv(String(form.elements.done_status_ids.value || "")));
  const activeStatusIds = parseCsv(String(form.elements.active_status_ids.value || ""));

  if (!mapping?.columns?.length) {
    return uniqueValues(activeStatusIds)
      .map((statusId) => ({ id: statusId, name: statusNames[statusId] || statusId }));
  }

  const startIndex = mapping.columns.findIndex((column) => (
    (column.status_ids || []).some((statusId) => startStatusIds.has(statusId))
  ));
  const doneIndex = mapping.columns.findIndex((column) => (
    (column.status_ids || []).some((statusId) => doneStatusIds.has(statusId))
  ));
  const fromIndex = startIndex >= 0 ? startIndex : 0;
  const toIndex = doneIndex >= fromIndex ? doneIndex : mapping.columns.length - 1;

  return uniqueValues(
    mapping.columns
      .slice(fromIndex, toIndex + 1)
      .flatMap((column) => column.status_ids || [])
      .filter((statusId) => !doneStatusIds.has(statusId))
  ).map((statusId) => ({ id: statusId, name: statusNames[statusId] || statusId }));
}

function aggregateCycleStatusSummary(details) {
  const statusOrder = cycleStatusDescriptors();
  return statusOrder.map(({ name }) => {
    let totalSeconds = 0;
    let issueCount = 0;

    details.forEach((detail) => {
      const statusData = detail.statuses?.[name];
      if (!statusData) {
        return;
      }
      totalSeconds += statusData.seconds || 0;
      issueCount += 1;
    });

    return {
      status: name,
      issueCount,
      averageDays: issueCount ? totalSeconds / issueCount / 86400 : 0,
    };
  });
}

function colorForStatusAverageDays(rows, currentRow) {
  if (!currentRow.issueCount || currentRow.averageDays <= 0) {
    return "rgba(106, 92, 84, 0.85)";
  }

  const positiveValues = rows
    .filter((row) => row.issueCount && row.averageDays > 0)
    .map((row) => row.averageDays)
    .sort((left, right) => left - right);

  if (positiveValues.length <= 1) {
    return "hsl(145 60% 34%)";
  }

  const min = positiveValues[0];
  const max = positiveValues.at(-1) || min;
  const median = percentileValue(positiveValues, 0.5) || min;
  const spread = max - min;
  const abnormalSpread = max - median;

  if (spread <= 0.75 || max <= median * 1.2) {
    const mildRatio = spread > 0 ? (currentRow.averageDays - min) / spread : 0;
    const hue = interpolateValue(145, 118, clampValue(mildRatio, 0, 1));
    return `hsl(${hue.toFixed(0)} 58% 34%)`;
  }

  const severity = abnormalSpread > 0
    ? clampValue((currentRow.averageDays - median) / abnormalSpread, 0, 1)
    : 0;

  let hue;
  if (severity <= 0.2) {
    hue = 145;
  } else if (severity <= 0.65) {
    hue = interpolateValue(145, 48, (severity - 0.2) / 0.45);
  } else {
    hue = interpolateValue(48, 8, (severity - 0.65) / 0.35);
  }

  return `hsl(${hue.toFixed(0)} 72% 36%)`;
}

function hasPendingCycleDateEntry() {
  return [cycleXStartInput, cycleXEndInput].some((input) => {
    if (!input.matches(":focus")) {
      return false;
    }
    if (input.validity.badInput) {
      return true;
    }
    if (!input.value) {
      return true;
    }
    return !parseIsoCalendarDate(input.value);
  });
}

function validateCycleControls() {
  const inputs = [
    [cycleXStartInput, "Date from"],
    [cycleXEndInput, "Date to"],
  ];

  inputs.forEach(([input]) => setCycleInputValidity(input));
  clearCycleControlsError();

  const errors = [];
  inputs.forEach(([input, label]) => {
    if (input.validity.badInput) {
      const message = `${label}: enter a valid calendar date.`;
      setCycleInputValidity(input, message);
      errors.push(message);
      return;
    }
    if (!input.value) {
      return;
    }
    if (!parseIsoCalendarDate(input.value)) {
      const message = `${label}: ${input.value} is not a real calendar date.`;
      setCycleInputValidity(input, message);
      errors.push(message);
    }
  });

  if (errors.length) {
    cycleControlsError.hidden = false;
    cycleControlsError.textContent = errors.join(" ");
    return { valid: false, message: errors[0] };
  }

  return { valid: true };
}

function issueUrlForPoint(target) {
  const config = configsById[currentConfigId];
  const baseUrl = config?.jira_base_url?.replace(/\/$/, "") || "";
  const issueKey = target.dataset.issueKey || "";
  if (!baseUrl || !issueKey) {
    return null;
  }
  return `${baseUrl}/browse/${encodeURIComponent(issueKey)}`;
}

function showCycleTooltip(target, event) {
  const issueKey = target.dataset.issueKey || "";
  const summary = target.dataset.summary || issueKey;
  const doneDate = target.dataset.doneDate || "";
  const cycle = target.dataset.cycle || "";

  cycleTooltip.innerHTML = `
    <strong>${escapeHtml(issueKey)}</strong>
    <p>${escapeHtml(summary)}</p>
    <p>Done ${escapeHtml(doneDate)} · Cycle ${escapeHtml(cycle)}</p>
    <p>Click the point to open this issue in Jira.</p>
  `;
  const shell = document.getElementById("cycle-trend-chart");
  if (cycleTooltip.parentElement !== shell) {
    shell.appendChild(cycleTooltip);
  }
  cycleTooltip.hidden = false;

  const shellRect = shell.getBoundingClientRect();
  const tooltipRect = cycleTooltip.getBoundingClientRect();
  const offsetX = event.clientX - shellRect.left + 14;
  const offsetY = event.clientY - shellRect.top - tooltipRect.height - 14;
  const left = Math.min(Math.max(offsetX, 8), Math.max(shellRect.width - tooltipRect.width - 8, 8));
  const top = offsetY < 8 ? Math.min(event.clientY - shellRect.top + 14, Math.max(shellRect.height - tooltipRect.height - 8, 8)) : offsetY;
  cycleTooltip.style.left = `${left}px`;
  cycleTooltip.style.top = `${top}px`;
}

function syncCycleControls(data) {
  const issues = data?.issues || [];
  const configuredRange = configDashboardDateDefaults();
  if (!issues.length) {
    cycleXStartInput.value = configuredRange.start || "";
    cycleXEndInput.value = configuredRange.end || "";
    cycleYMaxInput.value = "";
    cycleXStartInput.min = configuredRange.start || "";
    cycleXStartInput.max = configuredRange.end || "";
    cycleXEndInput.min = configuredRange.start || "";
    cycleXEndInput.max = configuredRange.end || "";
    cycleXStartInput.dataset.absoluteMin = configuredRange.start || "";
    cycleXStartInput.dataset.suggestedStart = configuredRange.start || "";
    cycleXEndInput.dataset.absoluteMax = configuredRange.end || "";
    cycleXEndInput.dataset.suggestedEnd = configuredRange.end || "";
    cycleXStartInput.disabled = !configuredRange.start && !configuredRange.end;
    cycleXEndInput.disabled = !configuredRange.start && !configuredRange.end;
    cycleYMaxInput.disabled = true;
    cycleFitP95Button.disabled = true;
    cycleShowAllButton.disabled = true;
    return;
  }

  cycleXStartInput.disabled = false;
  cycleXEndInput.disabled = false;
  cycleYMaxInput.disabled = false;
  cycleFitP95Button.disabled = false;
  cycleShowAllButton.disabled = false;

  const sorted = [...issues].sort((left, right) => new Date(left.end).getTime() - new Date(right.end).getTime());
  const issueMinDate = isoDate(sorted[0].end);
  const issueMaxDate = isoDate(sorted.at(-1).end);
  const minDate = configuredRange.start && configuredRange.start < issueMinDate ? configuredRange.start : issueMinDate;
  const maxDate = configuredRange.end && configuredRange.end > issueMaxDate ? configuredRange.end : issueMaxDate;
  const suggestedStartDate = configuredRange.start || isoDate(sorted[quantileIndex(sorted.length, 0.08)].end);
  const suggestedEndDate = configuredRange.end || issueMaxDate;
  const absoluteMaxHours = Math.max(...issues.map((item) => item.hours), 1);
  const suggestedMaxHours = data.summary?.p95 ? Math.max(1, data.summary.p95 / 3600) : absoluteMaxHours;
  const absoluteMaxDays = roundDaysUp(absoluteMaxHours);
  const suggestedMaxDays = roundDaysUp(suggestedMaxHours);

  cycleXStartInput.min = minDate;
  cycleXStartInput.max = maxDate;
  cycleXEndInput.min = minDate;
  cycleXEndInput.max = maxDate;
  cycleXStartInput.dataset.absoluteMin = minDate;
  cycleXStartInput.dataset.suggestedStart = suggestedStartDate;
  cycleXEndInput.dataset.absoluteMax = maxDate;
  cycleXEndInput.dataset.suggestedEnd = suggestedEndDate;
  cycleYMaxInput.min = "0.1";
  cycleYMaxInput.max = String(absoluteMaxDays);
  cycleYMaxInput.dataset.absoluteMax = String(absoluteMaxDays);
  cycleYMaxInput.dataset.suggestedMax = String(suggestedMaxDays);

  if (!cycleXStartInput.value || cycleXStartInput.value < minDate || cycleXStartInput.value > maxDate) {
    cycleXStartInput.value = suggestedStartDate;
  }
  if (!cycleXEndInput.value || cycleXEndInput.value > maxDate || cycleXEndInput.value < minDate) {
    cycleXEndInput.value = suggestedEndDate;
  }
  if (!cycleYMaxInput.value || Number(cycleYMaxInput.value) <= 0) {
    cycleYMaxInput.value = String(suggestedMaxDays);
  }
}

function buildCycleView(data) {
  const issues = visibleCycleIssues(data?.issues || []);
  if (!issues.length) {
    return {
      visibleIssues: [],
      totalCount: 0,
      xStart: null,
      xEnd: null,
      yMaxHours: null,
      hiddenByX: 0,
      hiddenByY: 0,
    };
  }

  const range = selectedDashboardDateRange(issues);
  const xStartMs = range?.xStartMs;
  const xEndMs = range?.xEndMs;
  const absoluteMaxDays = Number(cycleYMaxInput.dataset.absoluteMax || 0) || roundDaysUp(Math.max(...issues.map((item) => item.hours), 1));
  const yMaxHours = Math.max(daysToHours(Number(cycleYMaxInput.value) || absoluteMaxDays), 1);
  const issuesInXRange = filterItemsByDateRange(issues, (item) => item.end, range);
  const visibleIssues = issuesInXRange.filter((item) => item.hours <= yMaxHours);

  return {
    visibleIssues,
    totalCount: issues.length,
    xStart: range?.xStart || null,
    xEnd: range?.xEnd || null,
    xStartMs,
    xEndMs,
    yMaxHours,
    hiddenByX: issues.length - issuesInXRange.length,
    hiddenByY: issuesInXRange.length - visibleIssues.length,
  };
}

function issuesInCurrentCycleRange() {
  return selectedCycleIssuesInDateRange();
}

function renderCycle(data) {
  if (!data) {
    return;
  }
  updateHiddenIssuesControls();
  const summary = data.summary || {};
  const view = buildCycleView(data);
  const issuesInRange = issuesInCurrentCycleRange();
  renderCyclePercentiles(view.visibleIssues);
  document.getElementById("cycle-detail").textContent =
    summary.p85 == null
      ? "Each point shows one completed issue: X = done date, Y = cycle time."
      : `Showing ${view.visibleIssues.length}/${view.totalCount} issues · X ${view.xStart}..${view.xEnd} · Y max ${formatDuration(view.yMaxHours)} · hidden ${view.hiddenByX} outside range, ${view.hiddenByY} above scale`;

  if (!view.visibleIssues.length) {
    cycleTrendChart.innerHTML = '<p class="metric-detail">No issues match the selected axis range.</p>';
    hideCycleTooltip();
    hideCycleContextMenu();
    return;
  }

  renderScatterChart("cycle-trend-chart", view.visibleIssues, {
    minX: view.xStartMs,
    maxX: view.xEndMs,
    maxY: view.yMaxHours,
  });
  cycleTrendChart.appendChild(cycleTooltip);
  hideCycleTooltip();
  hideCycleContextMenu();
}

function renderThroughput(data) {
  const range = selectedDashboardDateRange(visibleCycleIssues(currentCycleData?.issues || []));
  const entries = aggregateThroughputData(
    filterItemsByDateRange(data?.events || [], (event) => event.completedAt, range)
      .filter((event) => !isIssueHidden(event.issueKey)),
    currentThroughputInterval
  );
  const totalCount = entries.reduce((sum, entry) => sum + entry.count, 0);
  const latestBucket = entries.at(-1) || null;
  document.getElementById("throughput-summary").textContent =
    entries.length ? `${formatTaskCount(totalCount)} total` : "No completions in range";
  document.getElementById("throughput-detail").textContent =
    entries.length
      ? `Y axis shows completed tasks, X axis shows ${throughputIntervalLabel(currentThroughputInterval)} in the selected date range. Hover a bar to see assignee breakdown.${latestBucket ? ` Latest ${latestBucket.fullLabel}: ${formatTaskCount(latestBucket.count)}.` : ""}`
      : "No throughput data in the selected date range.";
  renderBarChart(
    "throughput-chart",
    entries,
    (item) => item.count,
    (item) => item.label,
    {
      emptyMessage: "No throughput data in the selected date range.",
      yAxisTitle: "Tasks",
      xAxisTitle: currentThroughputInterval === "week" ? "Weeks" : "Months",
      svgClass: "chart-svg-large",
      tooltipHtml: (item) => {
        const assignees = Object.entries(item.byAssignee || {});
        return `
          <strong>${escapeHtml(item.fullLabel)}</strong>
          <ul class="chart-tooltip-list">
            ${assignees.map(([name, count]) => `<li><span>${escapeHtml(name)}</span><span>${escapeHtml(formatTaskCount(count))}</span></li>`).join("")}
          </ul>
          <p class="chart-tooltip-total">Total ${escapeHtml(formatTaskCount(item.count))}</p>
        `;
      },
    }
  );
}

function renderPhaseRatio(data) {
  const issueKeys = new Set(issuesInCurrentCycleRange().map((item) => item.issueKey));
  const filteredIssues = (data?.issues || []).filter((item) => issueKeys.has(item.issueKey));
  const statusSummary = filteredIssues.length ? aggregateCycleStatusSummary(filteredIssues) : [];
  document.getElementById("phase-status-detail").textContent =
    filteredIssues.length
      ? `Average time in each cycle status for ${filteredIssues.length} issues from the selected date range, in days.`
      : "No cycle status data in the selected date range.";
  renderRows(
    "phase-status-summary",
    statusSummary,
    (row) => `
      <div class="table-row">
        <div><strong>${row.status}</strong><span>${row.issueCount} issue${row.issueCount === 1 ? "" : "s"}</span></div>
        <div class="status-days-value" style="color: ${escapeHtml(colorForStatusAverageDays(statusSummary, row))}">${row.averageDays.toFixed(2)} d</div>
        <div>average in status</div>
      </div>
    `,
    "No cycle status data in the selected date range."
  );
}

function renderCfd(data) {
  const range = selectedDashboardDateRange(visibleCycleIssues(currentCycleData?.issues || []));
  const filteredPoints = filterItemsByDateRange(data?.points || [], (point) => startOfDayMs(point.day), range);
  const methodology = data.methodology || {};
  const meta = data.meta || {};
  const stackOrder = cfdStackOrder(data);
  const hiddenSeries = hiddenCfdSeriesForCurrentConfig();
  [...hiddenSeries].forEach((name) => {
    if (!stackOrder.includes(name)) {
      hiddenSeries.delete(name);
    }
  });
  const visibleStackOrder = stackOrder.filter((phase) => (
    !hiddenSeries.has(phase)
    && filteredPoints.some((point) => (point.current?.[phase] || 0) > 0)
  ));
  const renderedStackOrder = visibleStackOrder;
  const timezoneLabel = meta.timezone || "UTC";
  document.getElementById("cfd-detail").textContent =
    methodology.series && methodology.stacking
      ? `${methodology.series}. ${methodology.stacking}. Snapshots use ${timezoneLabel}.${hiddenSeries.size ? ` Hidden: ${hiddenSeries.size}.` : ""}`
      : "Daily end-of-day counts per configured workflow lane, stacked as a cumulative flow chart.";
  renderCfdLegend(renderedStackOrder);
  updateCfdHiddenControls(stackOrder);

  if (!filteredPoints.length) {
    hideCfdContextMenu();
    document.getElementById("cfd-chart").innerHTML = '<p class="metric-detail">No CFD data in the selected date range.</p>';
    return;
  }
  if (!visibleStackOrder.length && hiddenSeries.size) {
    hideCfdContextMenu();
    cfdLegend.innerHTML = "";
    document.getElementById("cfd-chart").innerHTML = '<p class="metric-detail">All visible CFD statuses are hidden. Reset hidden to show the chart again.</p>';
    return;
  }
  renderStackedAreaChart("cfd-chart", filteredPoints, renderedStackOrder, {
    emptyMessage: "No CFD data in the selected date range.",
  });
}

function renderRows(containerId, rows, builder, emptyMessage) {
  const container = document.getElementById(containerId);
  if (!rows || !rows.length) {
    container.innerHTML = `<p class="metric-detail">${emptyMessage}</p>`;
    return;
  }
  container.innerHTML = rows.map(builder).join("");
}

function rerenderDashboard() {
  if (!currentCycleData) {
    return;
  }
  if (hasPendingCycleDateEntry()) {
    [cycleXStartInput, cycleXEndInput].forEach((input) => setCycleInputValidity(input));
    clearCycleControlsError();
    hideCycleTooltip();
    hideThroughputTooltip();
    return;
  }
  const validation = validateCycleControls();
  if (!validation.valid) {
    hideCycleTooltip();
    hideThroughputTooltip();
    return;
  }
  clearCycleControlsError();
  hideThroughputTooltip();
  renderCycle(currentCycleData);
  renderThroughput(currentThroughputData);
  renderPhaseRatio(currentPhaseRatioData);
  renderCfd(currentCfdData);
}

async function loadMetrics(configId) {
  if (!configId) {
    setDashboardEmptyState({
      title: "Choose a saved config to view metrics.",
      detail: "Pick any config card above to load its charts and filters.",
    });
    return;
  }
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const [cycle, throughput, phaseRatio, cfd] = await Promise.all([
    request(`/api/metrics/cycle-time?configId=${encodeURIComponent(configId)}`),
    request(`/api/metrics/throughput?configId=${encodeURIComponent(configId)}`),
    request(`/api/metrics/phase-ratio?configId=${encodeURIComponent(configId)}`),
    request(`/api/metrics/cfd?configId=${encodeURIComponent(configId)}&timezone=${encodeURIComponent(browserTimezone)}`),
  ]);
  currentCycleData = cycle.data;
  currentThroughputData = throughput.data;
  currentPhaseRatioData = phaseRatio.data;
  currentCfdData = cfd.data;
  if (currentConfigId) {
    const currentIssueKeys = new Set((currentCycleData?.issues || []).map((issue) => issue.issueKey));
    hiddenIssueKeysByConfigId[currentConfigId] = new Set(
      [...hiddenIssueKeysForCurrentConfig()].filter((issueKey) => currentIssueKeys.has(issueKey))
    );
    const currentSeriesNames = new Set(cfdSeriesNames(currentCfdData));
    hiddenCfdSeriesByConfigId[currentConfigId] = new Set(
      [...hiddenCfdSeriesForCurrentConfig()].filter((seriesName) => currentSeriesNames.has(seriesName))
    );
  }
  syncCycleControls(currentCycleData);
  rerenderDashboard();
}

form.addEventListener("submit", (event) => {
  saveConfig(event).catch((error) => writeStatus(error.message));
});

testConnectionButton.addEventListener("click", () => {
  testConnection().catch((error) => writeStatus(error.message));
});

validateJqlButton.addEventListener("click", () => {
  validateJql().catch((error) => writeStatus(error.message));
});

loadStatusesButton.addEventListener("click", () => {
  loadProjectStatuses().catch((error) => writeStatus(error.message));
});

loadDemoButton.addEventListener("click", () => {
  loadDemo().catch((error) => writeStatus(error.message));
});

newConfigButton.addEventListener("click", () => {
  startNewConfiguration();
});

newConfigDashboardButton.addEventListener("click", () => {
  startNewConfiguration();
});

syncButton.addEventListener("click", () => {
  runSync().catch((error) => writeStatus(error.message));
});

refreshButton.addEventListener("click", () => {
  refreshConfigs().catch((error) => writeStatus(error.message));
});

openConfigurationButton.addEventListener("click", () => {
  setActiveTab("configuration");
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setActiveTab(button.dataset.tabButton);
  });
});

[cycleXStartInput, cycleXEndInput].forEach((input) => {
  input.addEventListener("input", () => {
    setCycleInputValidity(input);
    clearCycleControlsError();
    hideCycleTooltip();
    rerenderDashboard();
  });
  input.addEventListener("change", () => {
    rerenderDashboard();
  });
  input.addEventListener("blur", () => {
    const validation = validateCycleControls();
    if (!validation.valid) {
      input.reportValidity();
    }
    rerenderDashboard();
  });
});

cycleYMaxInput.addEventListener("input", () => {
  rerenderDashboard();
});

cycleYMaxInput.addEventListener("change", () => {
  rerenderDashboard();
});

cycleFitP95Button.addEventListener("click", () => {
  const rangeIssues = issuesInCurrentCycleRange();
  if (!rangeIssues.length) {
    rerenderDashboard();
    return;
  }
  const maxHoursInRange = Math.max(...rangeIssues.map((item) => item.hours), 1);
  cycleYMaxInput.value = String(roundDaysUp(maxHoursInRange));
  rerenderDashboard();
});

cycleShowAllButton.addEventListener("click", () => {
  if (!currentCycleData?.issues?.length) {
    return;
  }
  cycleXStartInput.value = cycleXStartInput.dataset.absoluteMin || cycleXStartInput.value;
  cycleXEndInput.value = cycleXEndInput.dataset.absoluteMax || cycleXEndInput.value;
  cycleYMaxInput.value = cycleYMaxInput.dataset.absoluteMax || cycleYMaxInput.value;
  rerenderDashboard();
});

throughputIntervalButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const nextInterval = button.dataset.throughputInterval || "month";
    if (nextInterval === currentThroughputInterval) {
      return;
    }
    currentThroughputInterval = nextInterval;
    syncThroughputIntervalControls();
    rerenderDashboard();
  });
});

cycleResetHiddenButton.addEventListener("click", () => {
  if (!currentConfigId) {
    return;
  }
  hiddenIssueKeysByConfigId[currentConfigId] = new Set();
  hideCycleContextMenu();
  rerenderDashboard();
});

cycleHidePointButton.addEventListener("click", () => {
  if (!currentConfigId || !cycleContextIssueKey) {
    hideCycleContextMenu();
    return;
  }
  hiddenIssueKeysForCurrentConfig().add(cycleContextIssueKey);
  hideCycleContextMenu();
  rerenderDashboard();
});

cycleTrendChart.addEventListener("mousemove", (event) => {
  const target = event.target.closest(".chart-point");
  if (!target) {
    hideCycleTooltip();
    return;
  }
  showCycleTooltip(target, event);
});

cycleTrendChart.addEventListener("mouseleave", () => {
  hideCycleTooltip();
});

cycleTrendChart.addEventListener("click", (event) => {
  const target = event.target.closest(".chart-point");
  if (!target) {
    hideCycleContextMenu();
    return;
  }
  hideCycleTooltip();
  showCycleContextMenu(target, event);
});

cfdLegend.addEventListener("click", (event) => {
  const target = event.target.closest("[data-cfd-series-name]");
  if (!target) {
    hideCfdContextMenu();
    return;
  }
  showCfdContextMenu(target, event);
});

cfdHideStatusButton.addEventListener("click", () => {
  if (!cfdContextSeriesName) {
    hideCfdContextMenu();
    return;
  }
  hiddenCfdSeriesForCurrentConfig().add(cfdContextSeriesName);
  hideCfdContextMenu();
  rerenderDashboard();
});

cfdResetHiddenButton.addEventListener("click", () => {
  hiddenCfdSeriesForCurrentConfig().clear();
  hideCfdContextMenu();
  rerenderDashboard();
});

document.addEventListener("click", (event) => {
  if (
    event.target.closest("#cycle-context-menu")
    || event.target.closest(".chart-point")
    || event.target.closest("#cfd-context-menu")
    || event.target.closest("[data-cfd-series-name]")
  ) {
    return;
  }
  hideCycleContextMenu();
  hideCfdContextMenu();
});

["project_keys", "issue_types", "sync_start_date", "sync_end_date", "extra_jql"].forEach((name) => {
  form.elements[name].addEventListener("input", () => {
    refreshGeneratedJqlPreview();
  });
  form.elements[name].addEventListener("change", () => {
    refreshGeneratedJqlPreview();
  });
});

form.elements.project_keys.addEventListener("focus", () => {
  if (!availableProjects.length) {
    loadProjects().catch(() => undefined);
  }
});

setActiveTab("dashboard");
syncThroughputIntervalControls();
renderBoardMapping(null);
renderProjectOptions([]);
setSyncStatus("idle", {
  progress: 0,
  message: "Start step 4 to load issues from Jira.",
  help: "The dashboard will refresh automatically when sync finishes.",
});
refreshGeneratedJqlPreview();
refreshConfigs().catch((error) => writeStatus(error.message));
