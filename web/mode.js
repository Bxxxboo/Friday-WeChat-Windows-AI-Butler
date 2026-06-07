/* ================================================================= *
 *  mode.js — 交互模式切换 Ask / Agent / Yolo
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) {
    console.error("mode.js: window.Friday 未初始化");
    return;
  }

  const MODE_HINT_KEYS = {
    ask: "mode.hint.ask",
    agent: "mode.hint.agent",
    yolo: "mode.hint.yolo",
    yolo_pending: "mode.hint.yolo_pending",
  };

  let interactionMode = "agent";
  let yoloUnlocked = false;
  let modePersistTimer = null;
  let pendingModeSwitch = null;

  const yoloModal = document.getElementById("yoloUnlockModal");
  const yoloConfirmBtn = document.getElementById("yoloUnlockConfirm");
  const yoloCancelBtn = document.getElementById("yoloUnlockCancel");

  function normalizeMode(value) {
    const mode = String(value || "agent").trim().toLowerCase();
    if (mode === "ask" || mode === "yolo") return mode;
    return "agent";
  }

  function yoloHintText() {
    if (interactionMode !== "yolo") {
      return F.t?.(MODE_HINT_KEYS[interactionMode]) || "";
    }
    return F.t?.(yoloUnlocked ? MODE_HINT_KEYS.yolo : MODE_HINT_KEYS.yolo_pending) || "";
  }

  function applyModeUi() {
    document.querySelectorAll(".mode-btn").forEach((btn) => {
      const active = btn.dataset.mode === interactionMode;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    const hint = document.getElementById("modeHint");
    if (hint) hint.textContent = yoloHintText();
    document.documentElement.dataset.interactionMode = interactionMode;
    document.documentElement.dataset.yoloUnlocked = interactionMode === "yolo" && yoloUnlocked ? "true" : "false";
  }

  function schedulePersistMode() {
    if (modePersistTimer) clearTimeout(modePersistTimer);
    modePersistTimer = setTimeout(() => {
      modePersistTimer = null;
      void F.apiFetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interaction_mode: interactionMode }),
      }).catch(() => {});
    }, 300);
  }

  async function ensureActiveSession() {
    if (F.activeSessionId) return F.activeSessionId;
    if (F.createSession) await F.createSession(false);
    return F.activeSessionId;
  }

  async function refreshYoloUnlockState() {
    const sessionId = F.activeSessionId;
    if (!sessionId || interactionMode !== "yolo") {
      yoloUnlocked = false;
      applyModeUi();
      return;
    }
    try {
      const res = await F.apiFetch(`/api/chat/yolo-unlock/${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        const data = await res.json();
        yoloUnlocked = Boolean(data.unlocked);
      }
    } catch {
      yoloUnlocked = false;
    }
    applyModeUi();
  }

  async function lockYoloForSession(sessionId) {
    if (!sessionId) return;
    try {
      await F.apiFetch(`/api/chat/yolo-unlock/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
      });
    } catch {
      // 忽略
    }
    yoloUnlocked = false;
  }

  function showYoloModal() {
    pendingModeSwitch = "yolo";
    yoloModal?.classList.remove("hidden");
  }

  function hideYoloModal() {
    pendingModeSwitch = null;
    yoloModal?.classList.add("hidden");
  }

  async function confirmYoloUnlock() {
    hideYoloModal();
    const sessionId = await ensureActiveSession();
    if (!sessionId) {
      F.setConnectionStatus?.("请先新建对话再开启 Yolo", false);
      return;
    }
    try {
      const res = await F.apiFetch("/api/chat/yolo-unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!res.ok) {
        F.setConnectionStatus?.("Yolo 授权失败", false);
        return;
      }
      yoloUnlocked = true;
      interactionMode = "yolo";
      applyModeUi();
      schedulePersistMode();
    } catch {
      F.setConnectionStatus?.("Yolo 授权失败", false);
    }
  }

  function setInteractionMode(mode, { persist = true, skipYoloGate = false } = {}) {
    const next = normalizeMode(mode);
    const prev = interactionMode;

    if (next === "yolo" && prev !== "yolo" && !skipYoloGate && !yoloUnlocked) {
      showYoloModal();
      return;
    }

    if (prev === "yolo" && next !== "yolo" && F.activeSessionId) {
      void lockYoloForSession(F.activeSessionId);
    }

    interactionMode = next;
    if (interactionMode !== "yolo") {
      yoloUnlocked = false;
    }
    applyModeUi();
    if (persist) schedulePersistMode();
    window.Friday?.refreshStatusBar?.();
  }

  function bindModeSwitch() {
    const root = document.getElementById("modeSwitch");
    if (!root) return;
    root.addEventListener("click", (event) => {
      const btn = event.target.closest(".mode-btn");
      if (!btn?.dataset.mode) return;
      setInteractionMode(btn.dataset.mode);
    });

    yoloConfirmBtn?.addEventListener("click", () => {
      void confirmYoloUnlock();
    });
    yoloCancelBtn?.addEventListener("click", () => {
      hideYoloModal();
    });
    yoloModal?.addEventListener("click", (event) => {
      if (event.target === yoloModal) hideYoloModal();
    });
  }

  F.getInteractionMode = () => interactionMode;
  F.isYoloUnlocked = () => interactionMode === "yolo" && yoloUnlocked;
  F.setInteractionMode = setInteractionMode;
  F.refreshYoloUnlockState = refreshYoloUnlockState;
  F.bindModeSwitch = bindModeSwitch;
  applyModeUi();
  window.addEventListener("friday:languagechange", () => applyModeUi());
})();
