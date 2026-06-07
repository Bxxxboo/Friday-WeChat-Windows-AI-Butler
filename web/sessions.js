/* ================================================================= *
 *  sessions.js — Friday 会话管理：CRUD + 列表/消息渲染
 *  依赖 utils.js（必须在其之后加载）
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) { console.error("sessions.js: window.Friday 未初始化，请确保 utils.js 先加载"); return; }

  /* ── 会话 API ── */

  async function fetchSessions() {
    const res = await F.apiFetchWithTimeout("/api/sessions", {}, 20000);
    if (!res.ok) throw new Error(`加载会话失败 (${res.status})`);
    const data = await res.json();
    F.sessions = data.sessions.map((item) => ({
      id: item.id,
      title: item.title,
      updatedAt: item.updated_at,
      createdAt: item.created_at,
      messages: [],
    }));
    F.activeSessionId = data.active_session_id || F.sessions[0]?.id || "";
    renderSessionList();
    if (F.activeSessionId) {
      await loadSessionDetail(F.activeSessionId, false);
    } else {
      await createSession(true);
    }
  }

  async function loadSessionDetail(sessionId, activate = true) {
    const res = await F.apiFetchWithTimeout(`/api/sessions/${sessionId}`, {}, 15000);
    if (!res.ok) throw new Error(`加载会话详情失败 (${res.status})`);
    const data = await res.json();
    let session = F.sessions.find((s) => s.id === sessionId);
    if (!session) {
      session = {
        id: data.id,
        title: data.title,
        updatedAt: data.updated_at,
        createdAt: data.created_at,
        messages: [],
      };
      F.sessions.unshift(session);
    }
    session.title = data.title;
    session.updatedAt = data.updated_at;
    session.messages = F.toUiMessages(data.messages);
    F.activeSessionId = sessionId;
    F.chatTitle.textContent = data.title;
    renderMessages(session.messages);
    renderSessionList();
    if (activate) {
      await F.apiFetch(`/api/sessions/${sessionId}/activate`, { method: "POST" });
    }
    F.updateInputState();
    void F.refreshYoloUnlockState?.();
    void F.refreshStatusBar?.();
  }

  async function createSession(switchTo = true) {
    const res = await F.apiFetchWithTimeout(
      "/api/sessions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: F.t?.("chat.title.default") || "新对话" }),
      },
      15000
    );
    if (!res.ok) throw new Error(`创建会话失败 (${res.status})`);
    const data = await res.json();
    const session = {
      id: data.id,
      title: data.title,
      updatedAt: data.updated_at,
      createdAt: data.created_at,
      messages: F.toUiMessages(data.messages),
    };
    F.sessions = F.sessions.filter((s) => s.id !== session.id);
    F.sessions.unshift(session);
    F.activeSessionId = session.id;
    F.chatTitle.textContent = session.title;
    renderSessionList();
    if (switchTo) {
      renderMessages(session.messages);
      await F.apiFetch(`/api/sessions/${session.id}/activate`, { method: "POST" });
    }
    F.updateInputState();
    void F.refreshYoloUnlockState?.();
    void F.refreshStatusBar?.();
    return session;
  }

  /* ── 渲染 ── */

  function renderSessionList() {
    F.sessionList.innerHTML = "";
    const sorted = [...F.sessions].sort((a, b) => b.updatedAt - a.updatedAt);
    sorted.forEach((session) => {
      const btn = document.createElement("button");
      btn.className = "session-item" + (session.id === F.activeSessionId ? " active" : "");
      btn.type = "button";

      const title = document.createElement("span");
      title.className = "session-item-title";
      title.textContent = session.title;

      const del = document.createElement("button");
      del.className = "session-item-delete";
      del.type = "button";
      del.title = "删除";
      del.textContent = "×";
      del.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteSession(session.id);
      });

      btn.appendChild(title);
      btn.appendChild(del);
      btn.addEventListener("click", () => switchSession(session.id));
      F.sessionList.appendChild(btn);
    });
  }

  function updateEmptyState(messages) {
    const hasMessages = messages && messages.length > 0;
    F.welcomePanel.classList.toggle("hidden", hasMessages);
    F.chatScroll.classList.toggle("hidden", !hasMessages);
  }

  function renderMessages(messages) {
    F.chatLog.innerHTML = "";
    messages.forEach((msg) => {
      const node = document.createElement("div");
      node.className = `message ${msg.kind}`;
      F.renderMessageBody(node, msg.kind, msg.text);
      F.chatLog.appendChild(node);
    });
    updateEmptyState(messages);
    F.scrollToBottom();
  }

  /* ── 切换 / 删除 ── */

  async function switchSession(sessionId) {
    if (sessionId === F.activeSessionId) return;
    if (F.busy) return;
    await loadSessionDetail(sessionId);
  }

  async function deleteSession(sessionId) {
    if (F.busy) return;
    const res = await F.apiFetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
    if (!res.ok) return;
    const data = await res.json();
    F.sessions = F.sessions.filter((s) => s.id !== sessionId);
    if (data.session) {
      const restored = {
        id: data.session.id,
        title: data.session.title,
        updatedAt: data.session.updated_at,
        createdAt: data.session.created_at,
        messages: F.toUiMessages(data.session.messages),
      };
      if (!F.sessions.some((s) => s.id === restored.id)) {
        F.sessions.unshift(restored);
      }
    }
    F.activeSessionId = data.active_session_id;
    renderSessionList();
    if (F.activeSessionId) {
      await loadSessionDetail(F.activeSessionId, false);
    }
  }

  /* ── 元数据更新 ── */

  function applySessionMeta(meta) {
    if (!meta) return;
    const session = F.getActiveSession();
    if (session) {
      session.title = meta.title;
      session.updatedAt = meta.updated_at;
    }
    F.chatTitle.textContent = meta.title;
    F.sessions = F.sessions.filter((s) => s.id !== meta.id);
    if (session) F.sessions.unshift(session);
    renderSessionList();
  }

  /* ── 挂载 ── */

  F.fetchSessions = fetchSessions;
  F.loadSessionDetail = loadSessionDetail;
  F.createSession = createSession;
  F.renderSessionList = renderSessionList;
  F.updateEmptyState = updateEmptyState;
  F.renderMessages = renderMessages;
  F.switchSession = switchSession;
  F.deleteSession = deleteSession;
  F.applySessionMeta = applySessionMeta;
})();
