/* ================================================================= *
 *  skills.js — 技能模板：欢迎页 chip / 斜杠补全
 *  依赖 utils.js；设置页管理见 extensions.js
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) { console.error("skills.js: window.Friday 未初始化"); return; }

  const suggestionsEl = document.querySelector(".welcome-suggestions");
  const slashMenu = document.getElementById("slashMenu");
  let allSkills = [];
  let slashIndex = -1;
  let slashMatches = [];

  function renderWelcomeGroups(groups) {
    if (!suggestionsEl) return;
    suggestionsEl.innerHTML = "";

    groups.forEach((group) => {
      const wrap = document.createElement("div");
      wrap.className = "chip-group";
      wrap.dataset.category = group.category;

      const label = document.createElement("span");
      label.className = "chip-group-label";
      label.textContent = group.label;

      const chips = document.createElement("div");
      chips.className = "welcome-chips";

      (group.skills || []).forEach((skill) => {
        chips.appendChild(makeChip(skill));
      });

      if (group.category === "daily") {
        chips.appendChild(makeActionChip("⏰ 设置定时任务", "schedules"));
        chips.appendChild(makeActionChip("🧩 管理扩展", "extensions"));
      }

      wrap.append(label, chips);
      suggestionsEl.appendChild(wrap);
    });
  }

  function makeChip(skill) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.dataset.prompt = skill.prompt;
    btn.dataset.skillId = skill.id;
    btn.textContent = `${skill.icon || "✨"} ${skill.label}`;
    return btn;
  }

  function makeActionChip(text, action) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.dataset.action = action;
    btn.textContent = text;
    return btn;
  }

  async function loadWelcomeChips() {
    try {
      const res = await F.apiFetch("/api/skills?grouped=true");
      const data = await res.json();
      const groups = (data.groups || []).filter((g) => g.category !== "plugin");
      allSkills = groups.flatMap((g) => g.skills || []);
      renderWelcomeGroups(groups);
    } catch (err) {
      console.error("加载技能失败", err);
    }
  }

  function hideSlashMenu() {
    slashIndex = -1;
    slashMatches = [];
    slashMenu?.classList.add("hidden");
    if (slashMenu) slashMenu.innerHTML = "";
  }

  function applySlashSelection(skill) {
    if (!skill || !F.chatInput) return;
    F.chatInput.value = skill.prompt;
    hideSlashMenu();
    F.updateInputState();
    F.chatInput.focus();
  }

  function highlightSlashItem(index) {
    if (!slashMenu) return;
    slashMenu.querySelectorAll(".slash-item").forEach((el, i) => {
      el.classList.toggle("active", i === index);
    });
  }

  function showSlashMenu(query) {
    if (!slashMenu) return;
    const q = query.toLowerCase();
    slashMatches = allSkills.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.prompt.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q)
    ).slice(0, 8);

    if (slashMatches.length === 0) {
      hideSlashMenu();
      return;
    }

    slashMenu.innerHTML = "";
    slashMatches.forEach((skill, idx) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "slash-item" + (idx === 0 ? " active" : "");
      item.innerHTML = `<span class="slash-item-icon">${skill.icon || "✨"}</span><span class="slash-item-text"><strong>${skill.label}</strong><small>${skill.prompt.slice(0, 48)}${skill.prompt.length > 48 ? "…" : ""}</small></span>`;
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        applySlashSelection(skill);
      });
      slashMenu.appendChild(item);
    });
    slashIndex = 0;
    slashMenu.classList.remove("hidden");
  }

  function handleSlashInput() {
    const input = F.chatInput;
    if (!input) return;
    const value = input.value;
    if (!value.startsWith("/")) {
      hideSlashMenu();
      return;
    }
    const query = value.slice(1).trim();
    if (allSkills.length === 0) {
      loadWelcomeChips().then(() => showSlashMenu(query));
      return;
    }
    showSlashMenu(query);
  }

  function onSlashKeydown(event) {
    if (slashMenu?.classList.contains("hidden") || slashMatches.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      slashIndex = (slashIndex + 1) % slashMatches.length;
      highlightSlashItem(slashIndex);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      slashIndex = (slashIndex - 1 + slashMatches.length) % slashMatches.length;
      highlightSlashItem(slashIndex);
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      applySlashSelection(slashMatches[slashIndex >= 0 ? slashIndex : 0]);
    } else if (event.key === "Escape") {
      hideSlashMenu();
    }
  }

  F.chatInput?.addEventListener("input", handleSlashInput);
  F.chatInput?.addEventListener("keydown", onSlashKeydown);
  F.chatInput?.addEventListener("blur", () => setTimeout(hideSlashMenu, 150));

  F.loadWelcomeChips = loadWelcomeChips;
  loadWelcomeChips();
})();
