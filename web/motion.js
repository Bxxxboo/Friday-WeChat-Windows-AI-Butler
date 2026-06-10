/* Friday motion — GSAP 动效（prefers-reduced-motion 自动降级） */
(function () {
  "use strict";

  const gsap = window.gsap;
  if (!gsap) {
    window.FridayMotion = {
      ready: false,
      animateBootExit: (cb) => { if (cb) cb(); },
      pulseMark: () => {},
      animateModalIn: () => {},
      animateModalOut: (el, cb) => { if (cb) cb(); },
      animateMessageIn: () => {},
      bindInteractions: () => {},
    };
    return;
  }

  gsap.defaults({ ease: "power2.out", duration: 0.42 });
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function animateBootExit(overlay, onComplete) {
    if (!overlay || reduced) {
      onComplete?.();
      return;
    }
    const mark = overlay.querySelector(".app-boot-mark");
    if (mark) gsap.killTweensOf(mark);
    const card = overlay.querySelector(".app-boot-card");
    const tl = gsap.timeline({ onComplete });
    tl.to(card || overlay, {
      y: -8,
      opacity: 0,
      scale: 0.98,
      duration: 0.38,
      ease: "power2.inOut",
    }).to(
      overlay,
      {
        opacity: 0,
        duration: 0.32,
        ease: "power1.inOut",
      },
      "-=0.12",
    );
  }

  function pulseMark(el) {
    if (!el || reduced) return;
    gsap.fromTo(
      el,
      { scale: 0.92, opacity: 0.6 },
      { scale: 1, opacity: 1, duration: 0.55, ease: "back.out(1.6)" },
    );
    gsap.to(el, {
      scale: 1.03,
      duration: 1.6,
      yoyo: true,
      repeat: -1,
      ease: "sine.inOut",
    });
  }

  function animateModalIn(modal) {
    if (!modal || reduced) return;
    const panel =
      modal.querySelector(".settings-window, .onboarding-window, .modal-card, .session-rename-window, .release-notes-card") ||
      modal.firstElementChild;
    gsap.fromTo(
      modal,
      { opacity: 0 },
      { opacity: 1, duration: 0.28, ease: "power1.out" },
    );
    if (panel) {
      gsap.fromTo(
        panel,
        { y: 16, opacity: 0, scale: 0.97 },
        { y: 0, opacity: 1, scale: 1, duration: 0.46, ease: "back.out(1.35)" },
      );
    }
  }

  function animateModalOut(modal, onComplete) {
    if (!modal || reduced) {
      onComplete?.();
      return;
    }
    const panel =
      modal.querySelector(".settings-window, .onboarding-window, .modal-card, .session-rename-window, .release-notes-card") ||
      modal.firstElementChild;
    const tl = gsap.timeline({ onComplete });
    if (panel) {
      tl.to(panel, { y: 10, opacity: 0, scale: 0.98, duration: 0.28, ease: "power2.in" });
    }
    tl.to(modal, { opacity: 0, duration: 0.22, ease: "power1.in" }, "-=0.08");
  }

  function animateMessageIn(node) {
    if (!node || reduced) return;
    gsap.fromTo(
      node,
      { y: 10, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.38, ease: "power2.out" },
    );
  }

  function bindInteractions() {
    if (reduced) return;

    document.addEventListener(
      "click",
      (ev) => {
        const btn = ev.target.closest(
          ".primary-btn, .ghost-btn, .new-chat-btn, .win-btn, .session-item, .chip-btn, .history-filter",
        );
        if (!btn || btn.disabled) return;
        gsap.fromTo(btn, { scale: 1 }, { scale: 0.96, duration: 0.08, yoyo: true, repeat: 1, ease: "power1.inOut" });
      },
      true,
    );
  }

  function init() {
    pulseMark(document.querySelector(".app-boot-mark"));
    bindInteractions();

    const observer = new MutationObserver((records) => {
      for (const rec of records) {
        rec.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (node.classList?.contains("message")) animateMessageIn(node);
          if (node.classList?.contains("modal") && !node.classList.contains("hidden")) {
            animateModalIn(node);
          }
        });
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  window.FridayMotion = {
    ready: true,
    animateBootExit,
    pulseMark,
    animateModalIn,
    animateModalOut,
    animateMessageIn,
    bindInteractions,
    init,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
