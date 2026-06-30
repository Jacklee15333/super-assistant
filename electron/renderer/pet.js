/* pet.js — 桌宠行为引擎
 *
 * 跑在桌宠那个透明小窗里。职责：
 *   · 渲染当前角色（来自 pet-characters.js），按帧推进动画
 *   · 状态机：idle 待着 → walk 溜达 → sleep 睡觉 → happy 被逗
 *   · 溜达：定时挑一个屏幕上的目标点，让「窗口」走过去（主进程移动窗口）
 *   · 拖动：按住拖 → 把窗口跟着挪；松手若几乎没动 = 点击 → 弹菜单
 *   · 菜单：打开主窗 / 说点什么 / 换形象 / 休息 / 收起
 *   · 喂文件：把文件拖到桌宠身上 → 交给主进程处理（视频链接去提取，其它进对话附件）
 *   · 任务状态：主进程推 busy/idle，桌宠头顶亮个小灯
 *
 * 与主进程的约定（window.petBridge，见 preload.js）：
 *   petBridge.ready()                      告诉主进程桌宠加载好了
 *   petBridge.getWorkArea() -> {x,y,width,height}
 *   petBridge.getBounds()   -> {x,y,width,height}  当前桌宠窗口位置
 *   petBridge.moveTo(x,y)                  移动桌宠窗口到屏幕坐标
 *   petBridge.openMain()                   把主窗拉到前面
 *   petBridge.hidePet()                    收起桌宠
 *   petBridge.getConfig() -> {character, custom, enabled}
 *   petBridge.setConfig(patch)             保存桌宠配置
 *   petBridge.feedFiles(paths)             把拖进来的文件交给主进程处理
 *   petBridge.onBusy(cb)                   主进程通知「任务进行中/结束」
 *   petBridge.onConfig(cb)                 主进程通知配置变了（在设置里改了形象）
 *   petBridge.onSay(cb)                    主进程让桌宠说一句话
 */

(function () {
  "use strict";

  var B = window.petBridge || null;        // 没有桥接也能跑（降级：不溜达，仅展示）
  var P = window.PetCharacters;

  var petEl = document.getElementById("pet");
  var bubbleEl = document.getElementById("bubble");
  var menuEl = document.getElementById("menu");
  var skinPanelEl = document.getElementById("skinPanel");
  var skinChipsEl = document.getElementById("skinChips");
  var busyDotEl = document.getElementById("busyDot");

  // ── 运行状态 ──
  var state = {
    characterId: "fox",
    custom: null,
    pose: "idle",          // idle | walk | sleep | happy
    facing: 1,             // 1 右 / -1 左
    frame: 0,
    blinkUntil: 0,
    sleeping: false,
    dragging: false,
    busy: false,
    workArea: { x: 0, y: 0, width: 1280, height: 800 },
    targetX: null,         // 溜达目标（屏幕坐标，窗口左上角的目标 x）
    speed: 1.4,            // 每帧像素
    nextActionAt: 0,       // 下次自动决策时间
    happyUntil: 0,
  };

  var character = P.getCharacter(state.characterId);
  document.documentElement.style.setProperty("--accent", character.accent);

  // ───────────────────────── 渲染循环 ─────────────────────────
  var lastBlink = 0;
  function tick(now) {
    state.frame += 1;

    // 眨眼：随机间隔
    if (!state.sleeping && now > lastBlink + 2600 + Math.random() * 2600) {
      lastBlink = now;
      state.blinkUntil = now + 130;
    }
    var blink = now < state.blinkUntil;

    // happy 计时结束 → 回到之前的姿态
    if (state.pose === "happy" && now > state.happyUntil) {
      state.pose = state.sleeping ? "sleep" : "idle";
    }

    // 自动行为决策（没在拖、没睡、没被逗时）
    if (!state.dragging && !state.sleeping && state.pose !== "happy" && now > state.nextActionAt) {
      decideNextAction(now);
    }

    // 溜达：朝目标移动窗口
    if (state.pose === "walk" && state.targetX != null && !state.dragging && B) {
      stepTowardTarget();
    }

    var pose = state.sleeping ? "sleep" : state.pose;
    petEl.innerHTML = character.svg({
      pose: pose, facing: state.facing, frame: state.frame, blink: blink
    });

    requestAnimationFrame(tick);
  }

  // 决定下一步：大概率溜达去某处，小概率发呆/卖萌
  function decideNextAction(now) {
    var roll = Math.random();
    if (!B) { state.nextActionAt = now + 3000; return; }
    if (roll < 0.55) {
      // 去屏幕上的一个新位置溜达
      var wa = state.workArea;
      var b = currentBounds();
      var margin = 40;
      var tx = wa.x + margin + Math.random() * (wa.width - b.width - margin * 2);
      state.targetX = Math.round(tx);
      state.facing = (state.targetX >= b.x) ? 1 : -1;
      state.pose = "walk";
      state.nextActionAt = now + 6000 + Math.random() * 4000;
    } else if (roll < 0.8) {
      // 原地发呆
      state.pose = "idle";
      state.nextActionAt = now + 2500 + Math.random() * 3000;
    } else {
      // 卖个萌
      poke(true);
      state.nextActionAt = now + 4000 + Math.random() * 3000;
    }
  }

  function currentBounds() {
    // 优先用主进程的真实窗口位置；拿不到就用缓存
    return state._bounds || { x: 200, y: 200, width: 160, height: 180 };
  }

  function stepTowardTarget() {
    var b = currentBounds();
    var dx = state.targetX - b.x;
    if (Math.abs(dx) <= state.speed * 2) {
      // 到了
      state.targetX = null;
      state.pose = "idle";
      state.nextActionAt = performance.now() + 1500 + Math.random() * 2000;
      return;
    }
    var dir = dx > 0 ? 1 : -1;
    state.facing = dir;
    var nx = b.x + dir * state.speed;
    // 轻微上下起伏已经在 SVG 里做了；这里只水平走
    var ny = b.y;
    b.x = nx; // 本地先更新，减少抖动
    B.moveTo(Math.round(nx), Math.round(ny));
  }

  // ───────────────────────── 说话气泡 ─────────────────────────
  var bubbleTimer = null;
  function say(text, ms) {
    if (!text) return;
    bubbleEl.textContent = text;
    bubbleEl.classList.add("show");
    if (bubbleTimer) clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(function () { bubbleEl.classList.remove("show"); },
      ms || 2600);
  }

  // 被逗 / 卖萌
  function poke(silent) {
    state.pose = "happy";
    state.happyUntil = performance.now() + 1400;
    if (!silent) {
      var hi = character.hello && character.hello.length
        ? character.hello[Math.floor(Math.random() * character.hello.length)]
        : "嗨~";
      say(hi);
    }
  }

  // ───────────────────────── 拖动 / 点击 ─────────────────────────
  var down = null;   // {sx, sy, bx, by, moved}
  petEl.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    closeMenus();
    var b = currentBounds();
    down = { sx: e.screenX, sy: e.screenY, bx: b.x, by: b.y, moved: false };
    state.dragging = true;
    petEl.classList.add("dragging");
    state.pose = state.sleeping ? "sleep" : "idle";
    state.targetX = null;
    e.preventDefault();
  });

  window.addEventListener("mousemove", function (e) {
    if (!down || !B) return;
    var ddx = e.screenX - down.sx;
    var ddy = e.screenY - down.sy;
    if (Math.abs(ddx) > 3 || Math.abs(ddy) > 3) down.moved = true;
    var nx = down.bx + ddx;
    var ny = down.by + ddy;
    var b = currentBounds();
    b.x = nx; b.y = ny;
    B.moveTo(Math.round(nx), Math.round(ny));
  });

  window.addEventListener("mouseup", function (e) {
    if (!down) return;
    state.dragging = false;
    petEl.classList.remove("dragging");
    var wasClick = !down.moved;
    down = null;
    if (wasClick) {
      // 点击：开/关菜单
      if (menuEl.classList.contains("show") || skinPanelEl.classList.contains("show")) {
        closeMenus();
      } else {
        poke();
        openMenu();
      }
    } else {
      // 拖完歇一下再溜达
      state.nextActionAt = performance.now() + 2000;
    }
  });

  // ───────────────────────── 菜单 ─────────────────────────
  function openMenu() {
    skinPanelEl.classList.remove("show");
    menuEl.classList.add("show");
  }
  function closeMenus() {
    menuEl.classList.remove("show");
    skinPanelEl.classList.remove("show");
  }

  menuEl.addEventListener("click", function (e) {
    var item = e.target.closest(".menu-item");
    if (!item) return;
    var act = item.dataset.act;
    if (act === "open") { closeMenus(); if (B) B.openMain(); }
    else if (act === "say") { closeMenus(); poke(); }
    else if (act === "skin") { openSkinPanel(); }
    else if (act === "sleep") { toggleSleep(); closeMenus(); }
    else if (act === "hide") { closeMenus(); if (B) B.hidePet(); }
  });

  function toggleSleep() {
    state.sleeping = !state.sleeping;
    state.pose = state.sleeping ? "sleep" : "idle";
    state.targetX = null;
    say(state.sleeping ? "那我先眯一会儿…" : "我醒啦！", 2000);
    state.nextActionAt = performance.now() + 3000;
  }

  // ───────────────────────── 换形象 ─────────────────────────
  function openSkinPanel() {
    menuEl.classList.remove("show");
    renderSkinChips();
    skinPanelEl.classList.add("show");
  }
  function renderSkinChips() {
    var list = P.listCharacters();
    skinChipsEl.innerHTML = list.map(function (c) {
      var active = (c.id === state.characterId) ? " active" : "";
      return '<div class="skin-chip' + active + '" data-id="' + c.id + '" style="--accent:' + c.accent + '">' +
        '<span class="sc-emoji">' + c.emoji + '</span>' +
        '<span class="sc-name">' + c.name + '</span></div>';
    }).join("");
    skinChipsEl.querySelectorAll(".skin-chip").forEach(function (chip) {
      chip.addEventListener("click", function () { switchCharacter(chip.dataset.id); });
    });
  }
  document.getElementById("skinBack").addEventListener("click", function () {
    skinPanelEl.classList.remove("show"); openMenu();
  });

  function switchCharacter(id) {
    state.characterId = id;
    character = P.getCharacter(id, state.custom);
    document.documentElement.style.setProperty("--accent", character.accent);
    renderSkinChips();
    poke();
    if (B) B.setConfig({ character: id });
    setTimeout(function () { closeMenus(); }, 350);
  }

  // ───────────────────────── 喂文件（拖拽到桌宠身上）─────────────────────────
  ["dragenter", "dragover"].forEach(function (ev) {
    window.addEventListener(ev, function (e) {
      e.preventDefault(); e.stopPropagation();
      petEl.classList.add("drop-hot");
    });
  });
  ["dragleave", "dragend"].forEach(function (ev) {
    window.addEventListener(ev, function (e) {
      e.preventDefault();
      if (e.relatedTarget == null) petEl.classList.remove("drop-hot");
    });
  });
  window.addEventListener("drop", function (e) {
    e.preventDefault(); e.stopPropagation();
    petEl.classList.remove("drop-hot");
    var paths = [];
    if (e.dataTransfer && e.dataTransfer.files) {
      for (var i = 0; i < e.dataTransfer.files.length; i++) {
        var f = e.dataTransfer.files[i];
        // Electron 下 File 对象带 .path
        if (f.path) paths.push(f.path);
      }
    }
    // 也支持拖进来的纯文本（比如视频链接）
    var text = "";
    try { text = e.dataTransfer.getData("text/plain") || ""; } catch (_) {}
    if (paths.length && B) {
      poke(true);
      say("吃进去啦，处理中~", 2600);
      B.feedFiles(paths);
    } else if (text && B) {
      poke(true);
      say("收到链接，处理中~", 2600);
      B.feedText(text);
    } else {
      say("咦？没吃到东西", 1800);
    }
  });

  // 点窗口空白处收起菜单
  document.getElementById("petStage").addEventListener("mousedown", function (e) {
    if (e.target.id === "petStage") closeMenus();
  });

  // ───────────────────────── 与主进程对接 ─────────────────────────
  function refreshBounds() {
    if (!B) return;
    B.getBounds().then(function (b) { if (b) state._bounds = b; }).catch(function () {});
  }

  function boot() {
    if (!B) {
      // 没有桥接：纯展示模式，至少让它呼吸
      requestAnimationFrame(tick);
      return;
    }
    Promise.all([B.getWorkArea(), B.getBounds(), B.getConfig()]).then(function (res) {
      var wa = res[0], b = res[1], cfg = res[2] || {};
      if (wa) state.workArea = wa;
      if (b) state._bounds = b;
      if (cfg.custom) state.custom = cfg.custom;
      if (cfg.character) {
        state.characterId = cfg.character;
        character = P.getCharacter(cfg.character, state.custom);
        document.documentElement.style.setProperty("--accent", character.accent);
      }
      state.nextActionAt = performance.now() + 1500;
      requestAnimationFrame(tick);
      // 开场打个招呼
      setTimeout(function () {
        var hi = character.hello && character.hello.length ? character.hello[0] : "我在啦~";
        say(hi, 2600);
      }, 600);
      B.ready();
    }).catch(function () {
      requestAnimationFrame(tick);
    });

    // 周期性校准窗口真实位置（防止拖动/系统缩放导致本地缓存漂移）
    setInterval(refreshBounds, 1500);

    // 主进程通知：任务进行中
    if (B.onBusy) B.onBusy(function (busy) {
      state.busy = !!busy;
      busyDotEl.classList.toggle("show", state.busy);
      if (busy && state.sleeping) { state.sleeping = false; state.pose = "idle"; }
    });
    // 主进程通知：配置变了（设置面板里改了形象）
    if (B.onConfig) B.onConfig(function (cfg) {
      if (!cfg) return;
      if (cfg.custom !== undefined) state.custom = cfg.custom;
      if (cfg.character && cfg.character !== state.characterId) {
        switchCharacterSilent(cfg.character);
      }
    });
    // 主进程让桌宠说话（早报、任务完成等）
    if (B.onSay) B.onSay(function (text) { if (text) { poke(true); say(text, 4000); } });
  }

  function switchCharacterSilent(id) {
    state.characterId = id;
    character = P.getCharacter(id, state.custom);
    document.documentElement.style.setProperty("--accent", character.accent);
  }

  boot();
})();
