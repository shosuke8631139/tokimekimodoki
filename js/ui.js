/* =========================================================
 * ときめきモドキ UI制御
 * 画面描画・イベントモーダルのキュー処理
 * =======================================================*/

(function () {
  const $ = (sel) => document.querySelector(sel);

  const titleScreen = $("#title-screen");
  const gameScreen = $("#game-screen");
  const endingScreen = $("#ending-screen");
  const modal = $("#event-modal");

  let eventQueue = [];
  let busy = false; // ターン処理中はコマンド禁止

  /* ---------- 描画 ---------- */

  function renderHud() {
    const s = Game.state;
    $("#date-display").textContent = Game.turnLabel(s.turn);
    $("#turn-display").textContent = `ターン ${Math.min(s.turn, MAX_TURN)} / ${MAX_TURN}`;
    $("#player-display").textContent = s.name;
  }

  function renderStats() {
    const s = Game.state.stats;
    const list = $("#stats-list");
    list.innerHTML = "";
    for (const key of ["study", "sport", "looks", "trivia", "stress"]) {
      const row = document.createElement("div");
      row.className = "stat-row";
      let cls = "stat-fill";
      if (key === "stress") {
        cls += s[key] >= 70 ? " stress-high" : s[key] >= 40 ? " stress-mid" : " stress-low";
      }
      row.innerHTML =
        `<div class="stat-label"><span>${STAT_NAMES[key]}</span><span>${s[key]}</span></div>` +
        `<div class="stat-bar"><div class="${cls}" style="width:${s[key]}%"></div></div>`;
      list.appendChild(row);
    }
  }

  function heartGauge(aff) {
    const n = Math.min(5, Math.floor(aff / 20) + (aff >= 10 ? 1 : 0));
    return "♥".repeat(n) + "♡".repeat(5 - n);
  }

  function renderChars() {
    const list = $("#chars-list");
    list.innerHTML = "";
    for (const c of CHARACTERS) {
      const ch = Game.state.chars[c.id];
      const card = document.createElement("div");
      card.className = "char-card" + (ch.met ? "" : " unmet");
      const bomb = ch.bomb > 0
        ? `<div class="char-bomb">💣</div><div class="bomb-count">爆発まで${ch.bomb}ターン!</div>`
        : "";
      const expr = ch.bomb > 0 ? "serious" : ch.aff >= 70 ? "happy" : "normal";
      card.innerHTML =
        `${bomb}<div class="char-portrait">${Portraits.svg(c.id, expr, 64)}</div>` +
        `<div class="char-name">${ch.met ? c.name : "???"}</div>` +
        `<div class="char-title">${ch.met ? c.title : "未遭遇"}</div>` +
        `<div class="char-hearts">${ch.met ? heartGauge(ch.aff) : ""}</div>`;
      card.title = ch.met ? c.desc : "まだ出会っていない";
      list.appendChild(card);
    }
  }

  function renderAll() {
    renderHud();
    renderStats();
    renderChars();
  }

  function addLog(text, cls) {
    const area = $("#log-area");
    const p = document.createElement("p");
    if (cls) p.className = cls;
    p.textContent = text;
    area.appendChild(p);
    area.scrollTop = area.scrollHeight;
  }

  function addTurnHeader() {
    addLog(`―― ${Game.turnLabel(Game.state.turn)} ――`, "log-sys");
  }

  function setCommandsEnabled(enabled) {
    document.querySelectorAll(".cmd-btn").forEach((b) => (b.disabled = !enabled));
  }

  /* ---------- イベントモーダル ---------- */

  function pumpEvents() {
    // しきい値イベントを都度チェックして追加
    eventQueue.push(...Game.checkThresholds());

    if (eventQueue.length === 0) {
      finishTurn();
      return;
    }
    showEvent(eventQueue.shift());
  }

  function showEvent(ev) {
    const pbox = $("#event-portrait");
    if (ev.charId) {
      pbox.innerHTML = Portraits.svg(ev.charId, "normal", 110);
    } else {
      pbox.textContent = "🏫";
    }
    $("#event-text").textContent = ev.text;

    const box = $("#event-choices");
    box.innerHTML = "";
    for (const choice of ev.choices) {
      const btn = document.createElement("button");
      btn.textContent = choice.label;
      btn.addEventListener("click", () => {
        const result = Game.resolveChoice(choice, ev.charId);
        showEventResult(result, ev.charId);
        renderAll();
      });
      box.appendChild(btn);
    }
    modal.classList.remove("hidden");
  }

  function showEventResult(result, charId) {
    if (charId) {
      const expr =
        result.affGain >= 9 ? "blush" :
        result.affGain >= 4 ? "happy" :
        result.affGain < 0 ? "shock" : "normal";
      $("#event-portrait").innerHTML = Portraits.svg(charId, expr, 110);
    }
    const textEl = $("#event-text");
    textEl.textContent = result.msg;
    if (result.deltas.length) {
      const meta = document.createElement("span");
      meta.className = "event-result-meta";
      meta.textContent = "▶ " + result.deltas.join(" / ");
      textEl.appendChild(meta);
    }
    const box = $("#event-choices");
    box.innerHTML = "";
    const ok = document.createElement("button");
    ok.className = "ok-btn";
    ok.textContent = "▼ つづく";
    ok.addEventListener("click", () => {
      modal.classList.add("hidden");
      pumpEvents();
    });
    box.appendChild(ok);
  }

  /* ---------- ターン進行 ---------- */

  function doCommand(cmd, dateCharId) {
    if (busy || Game.state.over) return;
    busy = true;
    setCommandsEnabled(false);
    $("#date-target").classList.add("hidden");

    addTurnHeader();
    const { logs, events } = Game.processCommand(cmd, dateCharId);
    logs.forEach((t) => addLog(t));
    renderAll();

    eventQueue = events;
    pumpEvents();
  }

  function finishTurn() {
    const { logs, endingKey } = Game.endTurn();
    logs.forEach((l) => addLog(l.text, l.cls));
    renderAll();

    if (endingKey) {
      setTimeout(() => showEnding(endingKey), 600);
      return;
    }
    busy = false;
    setCommandsEnabled(true);
  }

  /* ---------- エンディング ---------- */

  function showEnding(key) {
    const e = ENDINGS[key];
    gameScreen.classList.add("hidden");
    endingScreen.classList.remove("hidden");

    const typeEl = $("#ending-type");
    typeEl.textContent = `〜 ${e.type} 〜`;
    typeEl.classList.toggle("bad", e.bad);

    const pbox = $("#ending-portrait");
    if (ENDINGS[key] && Game.charById(key)) {
      pbox.innerHTML = Portraits.svg(key, "blush", 110);
    } else if (key === "harem") {
      pbox.innerHTML = CHARACTERS.map((c) => Portraits.svg(c.id, "shock", 80)).join("");
    } else if (key === "friend") {
      pbox.innerHTML = CHARACTERS.map((c) => Portraits.svg(c.id, "happy", 80)).join("");
    } else if (key === "bad") {
      pbox.innerHTML = Portraits.svg("hikari", "normal", 110);
    } else {
      pbox.innerHTML = "🌳";
    }
    $("#ending-title").textContent = e.title;

    const textBox = $("#ending-text");
    textBox.innerHTML = "";
    for (const para of e.text) {
      const p = document.createElement("p");
      p.textContent = para;
      textBox.appendChild(p);
    }

    const s = Game.state;
    const affList = CHARACTERS
      .map((c) => `${c.emoji}${c.name}:${s.chars[c.id].aff}`)
      .join(" / ");
    $("#ending-result").innerHTML =
      `<strong>${s.name}の3年間</strong><br>` +
      `学力${s.stats.study} 運動${s.stats.sport} 容姿${s.stats.looks} 雑学${s.stats.trivia} ストレス${s.stats.stress}<br>` +
      affList;
  }

  /* ---------- デート相手選択 ---------- */

  function openDatePicker() {
    const box = $("#date-target-buttons");
    box.innerHTML = "";
    let any = false;
    for (const c of CHARACTERS) {
      if (!Game.state.chars[c.id].met) continue;
      any = true;
      const btn = document.createElement("button");
      btn.innerHTML = `${Portraits.svg(c.id, "normal", 28)}<span>${c.name}</span>`;
      btn.addEventListener("click", () => doCommand("date", c.id));
      box.appendChild(btn);
    }
    if (!any) {
      addLog("まだ誘える相手がいない……まずは学校生活を始めよう。", "log-sys");
      return;
    }
    $("#date-target").classList.remove("hidden");
  }

  /* ---------- 初期化 ---------- */

  function startGame() {
    const name = $("#player-name").value.trim() || "主人公";
    Game.newGame(name);
    eventQueue = [];
    busy = false;

    titleScreen.classList.add("hidden");
    endingScreen.classList.add("hidden");
    gameScreen.classList.remove("hidden");
    $("#log-area").innerHTML = "";
    addLog(`私立きらめき暮第高校に入学した。ここから3年間(36ターン)の物語が始まる。`, "log-sys");
    setCommandsEnabled(true);
    renderAll();
  }

  // タイトル画面に3人の立ち絵を並べる
  $("#title-portraits").innerHTML = CHARACTERS
    .map((c) => Portraits.svg(c.id, "normal", 80))
    .join("");

  $("#start-btn").addEventListener("click", startGame);
  $("#restart-btn").addEventListener("click", () => {
    endingScreen.classList.add("hidden");
    titleScreen.classList.remove("hidden");
  });

  document.querySelectorAll(".cmd-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cmd = btn.dataset.cmd;
      if (cmd === "date") {
        openDatePicker();
      } else {
        doCommand(cmd);
      }
    });
  });

  $("#date-cancel").addEventListener("click", () => {
    $("#date-target").classList.add("hidden");
  });
})();
