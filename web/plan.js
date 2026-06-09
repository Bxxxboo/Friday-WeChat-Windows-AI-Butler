/* plan.js — 会话 Plan / Todo 面板 */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) return;

  const els = {
    panel: document.getElementById("planPanel"),
    toggle: document.getElementById("planPanelToggle"),
    body: document.getElementById("planPanelBody"),
    planInput: document.getElementById("planMarkdownInput"),
    todoList: document.getElementById("planTodoList"),
    todoEmpty: document.getElementById("planTodoEmpty"),
    todoBadge: document.getElementById("planTodoBadge"),
    saveBtn: document.getElementById("planSaveBtn"),
    saveHint: document.getElementById("planSaveHint"),
    addTodoBtn: document.getElementById("planAddTodoBtn"),
    parseBtn: document.getElementById("planParseBtn"),
    clearPlanBtn: document.getElementById("planClearPlanBtn"),
    clearTodosBtn: document.getElementById("planClearTodosBtn"),
  };

  let todos = [];
  let dragFromIndex = null;
  let executingTodoId = null;

  const NON_RUNNABLE_HINTS = [
    "从计划生成",
    "手动添加",
    "拖动排序",
    "勾选一项待办",
    "关闭面板",
    "新建对话",
    "粘贴本计划",
  ];

  function normalizeTodoImagePaths(raw) {
    if (Array.isArray(raw.image_paths)) {
      return raw.image_paths.filter(Boolean);
    }
    if (raw.image_path) return [raw.image_path];
    return [];
  }

  function normalizeTodoPreviewUrls(raw) {
    if (Array.isArray(raw.preview_urls)) {
      return raw.preview_urls.filter(Boolean);
    }
    if (raw.preview_url) return [raw.preview_url];
    return [];
  }

  function cloneTodoItem(raw) {
    const item = {
      id: raw.id || newTodoId(),
      text: raw.text || "",
      done: !!raw.done,
    };
    if (raw.queued) item.queued = true;
    const imagePaths = normalizeTodoImagePaths(raw);
    if (imagePaths.length) item.image_paths = imagePaths;
    const previewUrls = normalizeTodoPreviewUrls(raw);
    if (previewUrls.length) item.preview_urls = previewUrls;
    if (raw.running) item.running = !!raw.running;
    return item;
  }

  function serializeTodoItem(item) {
    const out = {
      id: item.id,
      text: item.text,
      done: !!item.done,
    };
    if (item.queued) out.queued = true;
    if (Array.isArray(item.image_paths) && item.image_paths.length) {
      out.image_paths = item.image_paths;
    }
    return out;
  }

  function isRunnableTodo(text) {
    const key = normalizeTodoText(text);
    if (!key) return false;
    return !NON_RUNNABLE_HINTS.some((hint) => key.includes(hint.toLowerCase()));
  }

  function getPendingRunnableTodos() {
    return todos.filter((item) => !item.done && isRunnableTodo(item.text));
  }

  function getPendingRunnableTodoCount() {
    return getPendingRunnableTodos().length;
  }

  function updateQueueIndicatorFromTodos() {
    F.updateQueueIndicator?.(getPendingRunnableTodoCount());
  }

  function pickNextRunnableTodo() {
    return getPendingRunnableTodos()[0] || null;
  }

  function setExecutingTodoId(id) {
    executingTodoId = id || null;
  }

  function getExecutingTodoId() {
    return executingTodoId;
  }

  function clearTodoRunningState() {
    if (executingTodoId) {
      const item = todos.find((t) => t.id === executingTodoId);
      if (item) item.running = false;
      executingTodoId = null;
      renderTodos();
    }
  }

  function markTodoDoneById(id) {
    const item = todos.find((t) => t.id === id);
    if (!item) return false;
    item.done = true;
    item.running = false;
    if (executingTodoId === id) executingTodoId = null;
    renderTodos();
    updateQueueIndicatorFromTodos();
    return true;
  }

  function defaultImagePrompt(count) {
    if (count > 1) return `请分析我粘贴的这 ${count} 张截图`;
    return "请分析我粘贴的这张截图";
  }

  async function addInstructionTodo({ text, imagePath = "", previewUrl = "", imagePaths = null, previewUrls = null }) {
    const clean = cleanTodoText(text);
    const paths = Array.isArray(imagePaths)
      ? imagePaths.filter(Boolean)
      : imagePath
        ? [imagePath]
        : [];
    const previews = Array.isArray(previewUrls)
      ? previewUrls.filter(Boolean)
      : previewUrl
        ? [previewUrl]
        : [];
    if (!clean && !paths.length) return null;
    const item = {
      id: newTodoId(),
      text: clean || defaultImagePrompt(paths.length),
      done: false,
      queued: true,
    };
    if (paths.length) item.image_paths = paths;
    if (previews.length) item.preview_urls = previews;
    todos.push(item);
    renderTodos();
    togglePanel(true);
    updateQueueIndicatorFromTodos();
    await savePlan({ silent: true });
    return todos[todos.length - 1].id;
  }

  async function processNextTodo() {
    if (F.busy) return false;
    const next = pickNextRunnableTodo();
    if (!next) {
      updateQueueIndicatorFromTodos();
      return false;
    }
    executingTodoId = next.id;
    next.running = true;
    renderTodos();
    await F.sendChat?.(next.text, true, {
      imagePaths: next.image_paths || [],
      previewUrls: next.preview_urls || [],
      todoId: next.id,
      showUserMessage: !next.queued,
    });
    return true;
  }

  function newTodoId() {
    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  }

  function normalizeTodoText(text) {
    return String(text || "")
      .replace(/(\*\*|__|`|\*|_)/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function cleanTodoText(text) {
    return String(text || "")
      .replace(/(\*\*|__|`|\*|_)/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function parsePlanToTodos(markdown) {
    const items = [];
    const seen = new Set();
    for (const rawLine of String(markdown || "").split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      let done = false;
      let text = "";
      const cb = line.match(/^[-*+]\s+\[([ xX])\]\s+(.+)$/);
      if (cb) {
        done = cb[1].toLowerCase() === "x";
        text = cb[2];
      } else {
        const num = line.match(/^\d+[.)]\s+(.+)$/);
        if (num) text = num[1];
        else {
          const bullet = line.match(/^[-*+]\s+(?!\[)(.+)$/);
          if (bullet) text = bullet[1];
        }
      }
      text = cleanTodoText(text);
      if (!text) continue;
      const key = text.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({ id: newTodoId(), text, done });
    }
    return items;
  }

  function autoCompleteUiTodosLocal() {
    const plan = String(els.planInput?.value || "").trim();
    const active = todos.filter((t) => String(t.text || "").trim());
    if (!active.length) return 0;
    let marked = 0;
    for (const item of active) {
      if (item.done) continue;
      const key = normalizeTodoText(item.text);
      if (!key) continue;
      if (key.includes("从计划生成") || key.includes("粘贴本计划")) {
        if (plan) {
          item.done = true;
          marked += 1;
        }
        continue;
      }
      if (key.includes("面板") && (key.includes("打开") || key.includes("计划") || key.includes("待办"))) {
        if (plan || active.length > 0) {
          item.done = true;
          marked += 1;
        }
        continue;
      }
      if (key.includes("手动添加") && active.length >= 2) {
        item.done = true;
        marked += 1;
        continue;
      }
      if (key.includes("拖动排序") || (key.includes("排序") && key.includes("保存"))) {
        item.done = true;
        marked += 1;
        continue;
      }
      if (key.includes("勾选") && (key.includes("徽章") || key.includes("待办"))) {
        if (active.some((t) => t.done)) {
          item.done = true;
          marked += 1;
        }
      }
    }
    if (marked > 0) {
      renderTodos();
      updateTodoMeta();
    }
    return marked;
  }

  function mergeTodosFromPlan() {
    const parsed = parsePlanToTodos(els.planInput?.value || "");
    if (!parsed.length) {
      flashHint("计划中未识别到列表项（支持 - [ ]、1.、- 条目）", false);
      return 0;
    }
    const known = new Set(todos.map((t) => normalizeTodoText(t.text)).filter(Boolean));
    let added = 0;
    for (const item of parsed) {
      const key = normalizeTodoText(item.text);
      if (!key || known.has(key)) continue;
      known.add(key);
      todos.push(item);
      added += 1;
    }
    renderTodos();
    autoCompleteUiTodosLocal();
    if (added > 0) flashHint(`已从计划添加 ${added} 项`, true);
    else flashHint("计划中的条目已在待办列表中", false);
    return added;
  }

  function flashHint(text, ok) {
    if (!els.saveHint) return;
    els.saveHint.textContent = text;
    els.saveHint.classList.toggle("is-ok", !!ok);
    clearTimeout(flashHint._timer);
    flashHint._timer = setTimeout(() => {
      if (els.saveHint && !els.body?.dataset.saved) {
        els.saveHint.textContent = "";
        els.saveHint.classList.remove("is-ok");
      }
    }, 2200);
  }

  function syncTodoListHeight() {
    if (!els.todoList) return;
    const count = todos.length;
    const visible = count > 0 ? Math.min(count, 4) : 0;
    els.todoList.style.setProperty("--plan-todo-visible-rows", String(visible));
  }

  function updateTodoMeta() {
    const total = todos.filter((t) => String(t.text || "").trim()).length;
    const done = todos.filter((t) => t.done && String(t.text || "").trim()).length;
    if (els.todoEmpty) {
      els.todoEmpty.classList.toggle("hidden", todos.length > 0);
    }
    if (els.todoBadge) {
      if (total > 0) {
        els.todoBadge.textContent = done === total ? `${done} 已完成` : `${done}/${total}`;
        els.todoBadge.classList.remove("hidden");
      } else {
        els.todoBadge.classList.add("hidden");
      }
    }
  }

  function moveTodo(from, to) {
    if (from === to || from < 0 || to < 0 || from >= todos.length || to >= todos.length) return;
    const [item] = todos.splice(from, 1);
    todos.splice(to, 0, item);
    renderTodos(to);
  }

  function createIconBtn(className, label, svg) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = className;
    btn.title = label;
    btn.setAttribute("aria-label", label);
    btn.innerHTML = svg;
    return btn;
  }

  function renderTodos(focusIndex = -1) {
    if (!els.todoList) return;
    els.todoList.innerHTML = "";
    todos.forEach((item, idx) => {
      const row = document.createElement("div");
      row.className = "plan-todo-row"
        + (item.done ? " is-done" : "")
        + (item.running ? " is-running" : "")
        + (item.queued ? " is-queued" : "");
      row.dataset.index = String(idx);

      const dragHandle = createIconBtn(
        "plan-todo-drag",
        "拖动排序",
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="9" cy="7" r="1.5"/><circle cx="15" cy="7" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="17" r="1.5"/><circle cx="15" cy="17" r="1.5"/></svg>'
      );
      dragHandle.draggable = true;
      dragHandle.addEventListener("dragstart", (event) => {
        dragFromIndex = idx;
        row.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(idx));
      });
      dragHandle.addEventListener("dragend", () => {
        dragFromIndex = null;
        row.classList.remove("is-dragging");
        els.todoList?.querySelectorAll(".plan-todo-row.is-drag-over").forEach((el) => {
          el.classList.remove("is-drag-over");
        });
      });

      row.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        row.classList.add("is-drag-over");
      });
      row.addEventListener("dragleave", () => row.classList.remove("is-drag-over"));
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        row.classList.remove("is-drag-over");
        const from = dragFromIndex ?? Number(event.dataTransfer.getData("text/plain"));
        if (Number.isNaN(from) || from === idx) return;
        moveTodo(from, idx);
      });

      const checkLabel = document.createElement("label");
      checkLabel.className = "plan-todo-check";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!item.done;
      cb.addEventListener("change", () => {
        todos[idx].done = cb.checked;
        row.classList.toggle("is-done", cb.checked);
        updateTodoMeta();
      });
      const box = document.createElement("span");
      box.className = "plan-todo-check-box";
      checkLabel.append(cb, box);

      const input = document.createElement("input");
      input.type = "text";
      input.className = "plan-todo-text";
      input.placeholder = "待办事项…";
      input.value = item.text || "";
      input.addEventListener("input", () => {
        todos[idx].text = input.value;
        updateTodoMeta();
        updateQueueIndicatorFromTodos();
      });
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          todos.splice(idx + 1, 0, { id: newTodoId(), text: "", done: false });
          renderTodos(idx + 1);
        }
      });

      const moveWrap = document.createElement("div");
      moveWrap.className = "plan-todo-move";
      const upBtn = createIconBtn(
        "plan-todo-move-btn",
        "上移",
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 14l6-6 6 6"/></svg>'
      );
      upBtn.disabled = idx === 0;
      upBtn.addEventListener("click", () => moveTodo(idx, idx - 1));
      const downBtn = createIconBtn(
        "plan-todo-move-btn",
        "下移",
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 10l6 6 6-6"/></svg>'
      );
      downBtn.disabled = idx === todos.length - 1;
      downBtn.addEventListener("click", () => moveTodo(idx, idx + 1));
      moveWrap.append(upBtn, downBtn);

      const removeBtn = createIconBtn(
        "plan-todo-remove",
        "删除",
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"></path></svg>'
      );
      removeBtn.addEventListener("click", () => {
        todos.splice(idx, 1);
        renderTodos(Math.min(idx, todos.length - 1));
      });

      row.append(dragHandle, checkLabel, input, moveWrap, removeBtn);
      els.todoList.appendChild(row);

      if (idx === focusIndex) input.focus();
    });
    updateTodoMeta();
    syncTodoListHeight();
    updateQueueIndicatorFromTodos();
  }

  function showSavedHint() {
    if (!els.body || !els.saveHint) return;
    els.body.dataset.saved = "1";
    els.saveHint.textContent = "已保存";
    els.saveHint.classList.add("is-ok");
    setTimeout(() => {
      if (els.body) delete els.body.dataset.saved;
      if (els.saveHint) {
        els.saveHint.textContent = "";
        els.saveHint.classList.remove("is-ok");
      }
    }, 1600);
  }

  async function loadPlan(sessionId) {
    if (!sessionId || !els.planInput) return;
    try {
      const res = await F.apiFetch(`/api/sessions/${sessionId}/plan`);
      if (!res.ok) return;
      const data = await res.json();
      els.planInput.value = data.plan_markdown || "";
      todos = Array.isArray(data.todos) ? data.todos.map((t) => cloneTodoItem(t)) : [];
      renderTodos();
    } catch (_err) {
      /* ignore */
    }
  }

  async function savePlan(options = {}) {
    if (!F.activeSessionId) return false;
    autoCompleteUiTodosLocal();
    todos = todos.filter((t) => String(t.text || "").trim());
    renderTodos();
    const res = await F.apiFetch(`/api/sessions/${F.activeSessionId}/plan`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_markdown: els.planInput?.value || "",
        todos: todos.map((t) => serializeTodoItem(t)),
      }),
    });
    if (res.ok) {
      try {
        const data = await res.json();
        if (Array.isArray(data.todos)) {
          todos = data.todos.map((t) => cloneTodoItem(t));
          renderTodos();
        }
      } catch (_err) {
        /* ignore */
      }
      if (!options.silent) showSavedHint();
      return true;
    }
    return false;
  }

  async function clearPlan() {
    const text = String(els.planInput?.value || "").trim();
    if (!text) {
      flashHint("计划已是空的", false);
      return;
    }
    if (!window.confirm("确定清空任务计划？")) return;
    if (els.planInput) els.planInput.value = "";
    if (await savePlan({ silent: true })) flashHint("已清空计划", true);
  }

  async function clearTodos() {
    const active = todos.filter((t) => String(t.text || "").trim());
    if (!active.length) {
      flashHint("待办已是空的", false);
      return;
    }
    if (!window.confirm("确定清空全部待办？")) return;
    todos = [];
    renderTodos();
    if (await savePlan({ silent: true })) flashHint("已清空待办", true);
  }

  function togglePanel(force) {
    if (!els.panel || !els.body) return;
    const open = force != null ? force : els.panel.classList.contains("collapsed");
    els.panel.classList.toggle("collapsed", !open);
    if (els.toggle) els.toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) autoCompleteUiTodosLocal();
  }

  if (els.toggle) {
    els.toggle.addEventListener("click", () => togglePanel());
  }
  if (els.saveBtn) {
    els.saveBtn.addEventListener("click", () => void savePlan());
  }
  if (els.addTodoBtn) {
    els.addTodoBtn.addEventListener("click", () => {
      todos.push({ id: newTodoId(), text: "", done: false });
      renderTodos(todos.length - 1);
    });
  }
  if (els.parseBtn) {
    els.parseBtn.addEventListener("click", () => mergeTodosFromPlan());
  }
  if (els.clearPlanBtn) {
    els.clearPlanBtn.addEventListener("click", () => void clearPlan());
  }
  if (els.clearTodosBtn) {
    els.clearTodosBtn.addEventListener("click", () => void clearTodos());
  }

  F.applySessionPlan = (data) => {
    if (els.planInput) els.planInput.value = data?.plan_markdown || "";
    todos = Array.isArray(data?.todos) ? data.todos.map((t) => cloneTodoItem(t)) : [];
    if (!F.busy) executingTodoId = null;
    renderTodos();
  };
  F.loadSessionPlan = loadPlan;
  F.saveSessionPlan = savePlan;
  F.mergeTodosFromPlan = mergeTodosFromPlan;
  F.addInstructionTodo = addInstructionTodo;
  F.processNextTodo = processNextTodo;
  F.getPendingRunnableTodoCount = getPendingRunnableTodoCount;
  F.markTodoDoneById = markTodoDoneById;
  F.getExecutingTodoId = getExecutingTodoId;
  F.setExecutingTodoId = setExecutingTodoId;
  F.clearTodoRunningState = clearTodoRunningState;
  F.updateQueueIndicatorFromTodos = updateQueueIndicatorFromTodos;
})();
