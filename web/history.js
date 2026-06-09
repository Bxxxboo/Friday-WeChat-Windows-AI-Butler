/* ================================================================= *
 *  history.js — 操作历史时间线（右侧抽屉）
 *  依赖 utils.js
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) { console.error("history.js: window.Friday 未初始化"); return; }

  const drawer = document.getElementById("historyDrawer");
  const backdrop = document.getElementById("historyBackdrop");
  const listEl = document.getElementById("historyList");
  const emptyEl = document.getElementById("historyEmpty");
  const filterBtns = document.querySelectorAll("[data-history-filter]");
  const toolFilter = document.getElementById("historyToolFilter");
  const riskFilter = document.getElementById("historyRiskFilter");
  const triggerFilter = document.getElementById("historyTriggerFilter");

  let filter = "writes";

  function formatTime(ts) {
    const d = new Date(ts * 1000);
    const now = new Date();
    const isToday =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    const time = d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    if (isToday) return `今天 ${time}`;
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday =
      d.getFullYear() === yesterday.getFullYear() &&
      d.getMonth() === yesterday.getMonth() &&
      d.getDate() === yesterday.getDate();
    if (isYesterday) return `昨天 ${time}`;
    return `${d.getMonth() + 1}/${d.getDate()} ${time}`;
  }

  function triggerLabel(trigger) {
    return trigger === "scheduled" ? "定时" : "对话";
  }

  function buildQueryParams() {
    const params = new URLSearchParams({ limit: "80" });
    if (filter === "writes") params.set("writes_only", "true");
    const tool = toolFilter?.value || "";
    const risk = riskFilter?.value || "";
    const trigger = triggerFilter?.value || "";
    if (tool) params.set("tool", tool);
    if (risk) params.set("risk", risk);
    if (trigger) params.set("trigger", trigger);
    return params;
  }

  function exportUrl(format) {
    const params = buildQueryParams();
    params.set("format", format);
    params.set("limit", "500");
    return `/api/operations/export?${params}`;
  }

  async function replayOperation(id) {
    try {
      const res = await F.apiFetch(`/api/operations/${id}/replay`, { method: "POST" });
      const data = await res.json();
      if (data.prompt) {
        closeHistory();
        F.chatInput.value = data.prompt;
        F.updateInputState();
        F.chatInput.focus();
      }
    } catch (err) {
      console.error(err);
    }
  }

  function renderItem(op) {
    const li = document.createElement("li");
    li.className = "history-item" + (op.success ? "" : " history-item-fail");

    const head = document.createElement("div");
    head.className = "history-item-head";

    const badge = document.createElement("span");
    badge.className = "history-badge history-badge-" + (op.risk || "read");
    badge.textContent = F.nameToLabel(op.tool);

    const meta = document.createElement("span");
    meta.className = "history-meta";
    meta.textContent = `${formatTime(op.ts)} · ${triggerLabel(op.trigger)}`;

    head.appendChild(badge);
    head.appendChild(meta);

    const summary = document.createElement("p");
    summary.className = "history-summary";
    summary.textContent = op.summary || op.result || "";

    li.appendChild(head);
    li.appendChild(summary);

    if (op.result && op.result !== op.summary) {
      const detail = document.createElement("p");
      detail.className = "history-detail";
      detail.textContent = op.result;
      li.appendChild(detail);
    }

    if (op.approved === false) {
      const tag = document.createElement("span");
      tag.className = "history-tag history-tag-deny";
      tag.textContent = "已拒绝";
      head.appendChild(tag);
    }

    const actions = document.createElement("div");
    actions.className = "history-item-actions";
    const replayBtn = document.createElement("button");
    replayBtn.type = "button";
    replayBtn.className = "ghost-btn history-replay-btn";
    replayBtn.textContent = "重放";
    replayBtn.addEventListener("click", () => replayOperation(op.id));
    actions.appendChild(replayBtn);
    li.appendChild(actions);

    return li;
  }

  async function fetchHistory() {
    if (!listEl) return;
    listEl.innerHTML = "";
    emptyEl?.classList.add("hidden");
    if (emptyEl) {
      emptyEl.textContent = "暂无记录。完成一次文件整理后会出现在这里。";
    }

    try {
      const res = await F.apiFetch(`/api/operations?${buildQueryParams()}`);
      const data = await res.json();
      const ops = data.operations || [];
      if (ops.length === 0) {
        emptyEl?.classList.remove("hidden");
        return;
      }
      const ul = document.createElement("ul");
      ul.className = "history-timeline";
      ops.forEach((op) => ul.appendChild(renderItem(op)));
      listEl.appendChild(ul);
    } catch (err) {
      console.error(err);
      if (emptyEl) {
        emptyEl.textContent = "加载失败，请稍后重试";
        emptyEl.classList.remove("hidden");
      }
    }
  }

  function openHistory() {
    drawer?.classList.remove("hidden");
    backdrop?.classList.remove("hidden");
    fetchHistory();
  }

  function closeHistory() {
    drawer?.classList.add("hidden");
    backdrop?.classList.add("hidden");
  }

  function setFilter(next) {
    filter = next;
    filterBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.historyFilter === next);
    });
    fetchHistory();
  }

  function onOperationLogged() {
    if (drawer && !drawer.classList.contains("hidden")) {
      fetchHistory();
    }
  }

  document.getElementById("openHistoryBtn")?.addEventListener("click", openHistory);
  document.getElementById("closeHistoryBtn")?.addEventListener("click", closeHistory);
  backdrop?.addEventListener("click", closeHistory);
  document.getElementById("clearHistoryBtn")?.addEventListener("click", async () => {
    if (!confirm("确定清空全部操作历史？")) return;
    await F.apiFetch("/api/operations", { method: "DELETE" });
    fetchHistory();
  });

  document.getElementById("exportHistoryJsonBtn")?.addEventListener("click", () => {
    window.open(exportUrl("json"), "_blank");
  });
  document.getElementById("exportHistoryCsvBtn")?.addEventListener("click", () => {
    window.open(exportUrl("csv"), "_blank");
  });

  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => setFilter(btn.dataset.historyFilter));
  });

  [toolFilter, riskFilter, triggerFilter].forEach((el) => {
    el?.addEventListener("change", fetchHistory);
  });

  F.openHistory = openHistory;
  F.closeHistory = closeHistory;
  F.onOperationLogged = onOperationLogged;
})();
