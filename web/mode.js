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
  const modeSwitchGlider = document.getElementById("modeSwitchGlider");

  let modeTooltip = document.getElementById("modeTooltip");
  if (!modeTooltip) {
    modeTooltip = document.createElement("div");
    modeTooltip.id = "modeTooltip";
    modeTooltip.className = "mode-tooltip hidden";
    modeTooltip.setAttribute("role", "tooltip");
    modeTooltip.setAttribute("aria-hidden", "true");
    document.body.appendChild(modeTooltip);
  }

  let tooltipTimer = null;
  let tooltipAnchor = null;

  function normalizeMode(value) {
    const mode = String(value || "agent").trim().toLowerCase();
    if (mode === "ask" || mode === "yolo") return mode;
    return "agent";
  }

  function hintForMode(mode) {
    if (mode === "yolo") {
      if (interactionMode === "yolo" && !yoloUnlocked) {
        return F.t?.(MODE_HINT_KEYS.yolo_pending) || "";
      }
      return F.t?.(MODE_HINT_KEYS.yolo) || "";
    }
    return F.t?.(MODE_HINT_KEYS[mode]) || "";
  }

  function hideModeTooltip() {
    if (tooltipTimer) {
      clearTimeout(tooltipTimer);
      tooltipTimer = null;
    }
    tooltipAnchor = null;
    if (!modeTooltip) return;
    modeTooltip.classList.remove("is-visible");
    modeTooltip.classList.add("hidden");
    modeTooltip.setAttribute("aria-hidden", "true");
  }

  function positionModeTooltip(anchor) {
    if (!modeTooltip || !anchor) return;
    modeTooltip.classList.remove("hidden");
    const rect = anchor.getBoundingClientRect();
    const tipRect = modeTooltip.getBoundingClientRect();
    const left = rect.left + rect.width / 2 - tipRect.width / 2;
    const top = rect.top - tipRect.height - 10;
    const maxLeft = window.innerWidth - tipRect.width - 8;
    const clampedLeft = Math.max(8, Math.min(left, maxLeft));
    modeTooltip.style.left = `${clampedLeft}px`;
    modeTooltip.style.top = `${Math.max(8, top)}px`;
    const arrowLeft = rect.left + rect.width / 2 - clampedLeft;
    modeTooltip.style.setProperty("--tip-arrow-left", `${arrowLeft}px`);
  }

  function showModeTooltip(anchor, mode) {
    if (!modeTooltip || !anchor) return;
    const text = hintForMode(mode);
    if (!text) return;
    tooltipAnchor = anchor;
    modeTooltip.textContent = text;
    modeTooltip.setAttribute("aria-hidden", "false");
    positionModeTooltip(anchor);
    requestAnimationFrame(() => {
      modeTooltip.classList.add("is-visible");
    });
  }

  function scheduleModeTooltip(anchor, mode) {
    hideModeTooltip();
    tooltipTimer = setTimeout(() => {
      tooltipTimer = null;
      showModeTooltip(anchor, mode);
    }, 1000);
  }

  function updateModeGlider() {
    const root = document.getElementById("modeSwitch");
    const active = root?.querySelector(".mode-btn.active");
    if (!modeSwitchGlider || !root || !active) return;
    const rootRect = root.getBoundingClientRect();
    const btnRect = active.getBoundingClientRect();
    modeSwitchGlider.style.width = `${btnRect.width}px`;
    modeSwitchGlider.style.transform = `translateX(${btnRect.left - rootRect.left}px)`;
  }

  function applyModeUi() {
    document.querySelectorAll(".mode-btn").forEach((btn) => {
      const active = btn.dataset.mode === interactionMode;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    updateModeGlider();
    if (tooltipAnchor && modeTooltip?.classList.contains("is-visible")) {
      positionModeTooltip(tooltipAnchor);
    }
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

    root.querySelectorAll(".mode-btn").forEach((btn) => {
      const mode = btn.dataset.mode;
      if (!mode) return;
      btn.addEventListener("mouseenter", () => scheduleModeTooltip(btn, mode));
      btn.addEventListener("mouseleave", hideModeTooltip);
      btn.addEventListener("focus", () => scheduleModeTooltip(btn, mode));
      btn.addEventListener("blur", hideModeTooltip);
    });
    window.addEventListener("scroll", hideModeTooltip, true);
    window.addEventListener("resize", () => {
      updateModeGlider();
      if (tooltipAnchor && modeTooltip?.classList.contains("is-visible")) {
        positionModeTooltip(tooltipAnchor);
      } else {
        hideModeTooltip();
      }
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
  requestAnimationFrame(updateModeGlider);
  window.addEventListener("friday:languagechange", () => {
    hideModeTooltip();
    applyModeUi();
    F.refreshComposerModelSwitch?.();
  });
})();
