/* =========================================================
 * 人生モドキ 画面制御
 * ルーレット・メッセージ送り・パネル更新・進行ループ・結果発表
 * =======================================================*/

const UI = {
  fast: false,
  spinning: false,
  wheelAngle: 0,
  rafId: 0,

  el: {},

  init() {
    const id = (s) => document.getElementById(s);
    this.el = {
      title: id("title-screen"),
      game: id("game-screen"),
      result: id("result-screen"),
      nameInput: id("player-name"),
      startBtn: id("start-btn"),
      countBtns: document.querySelectorAll("[data-count]"),
      hudTurn: id("hud-turn"),
      hudCell: id("hud-cell"),
      fastToggle: id("fast-toggle"),
      players: id("players"),
      log: id("log-area"),
      rouArea: id("roulette-area"),
      wheel: id("wheel"),
      wheelNum: id("wheel-num"),
      spinBtn: id("spin-btn"),
      msgBox: id("msg-box"),
      msgText: id("msg-text"),
      choices: id("choices"),
      resultBody: id("result-body"),
      restartBtn: id("restart-btn"),
    };

    this.buildWheel();

    let count = 4;
    this.el.countBtns.forEach((b) => {
      b.addEventListener("click", () => {
        count = Number(b.dataset.count);
        this.el.countBtns.forEach((x) => x.classList.toggle("on", x === b));
      });
    });

    this.el.startBtn.addEventListener("click", () => this.start(count));
    this.el.restartBtn.addEventListener("click", () => location.reload());
    this.el.fastToggle.addEventListener("change", (e) => { this.fast = e.target.checked; });

    document.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " " && e.key !== "z" && e.key !== "Z") return;
      if (!this.el.title.classList.contains("hidden")) { this.el.startBtn.click(); return; }
      e.preventDefault();
      if (!this.el.msgBox.classList.contains("hidden")) this.el.msgBox.click();
      else if (!this.el.rouArea.classList.contains("hidden")) this.el.spinBtn.click();
    });
  },

  /* ---------- ルーレット ---------- */

  buildWheel() {
    const stops = [];
    const colors = ["#f7f3e3", "#e8dcb8"];
    for (let i = 0; i < 10; i++) {
      stops.push(`${colors[i % 2]} ${i * 36}deg ${(i + 1) * 36}deg`);
    }
    this.el.wheel.style.background = `conic-gradient(${stops.join(",")})`;
    for (let i = 0; i < 10; i++) {
      const span = document.createElement("span");
      span.className = "wheel-label";
      span.textContent = i + 1;
      const a = i * 36 + 18;
      span.style.transform = `rotate(${a}deg) translateY(-46px) rotate(${-a}deg)`;
      this.el.wheel.appendChild(span);
    }
  },

  /* 針(真上)の下にある数字。時計回りに 1〜10。 */
  numberAt(angle) {
    const local = ((-angle % 360) + 360) % 360;
    return Math.floor(local / 36) + 1;
  },

  setWheel(angle) {
    this.wheelAngle = angle;
    this.el.wheel.style.transform = `rotate(${angle}deg)`;
  },

  spin(p) {
    this.show("roulette");
    this.el.spinBtn.textContent = "まわす";
    this.el.spinBtn.disabled = false;
    this.el.wheelNum.textContent = "?";

    return new Promise((resolve) => {
      const startSpin = () => {
        this.spinning = true;
        this.el.spinBtn.textContent = "とめる!";
        let last = performance.now();
        const loop = (now) => {
          if (!this.spinning) return;
          this.setWheel((this.wheelAngle + (now - last) * 0.75) % 360);  // 約750度/秒
          this.el.wheelNum.textContent = this.numberAt(this.wheelAngle);
          last = now;
          this.rafId = requestAnimationFrame(loop);
        };
        this.rafId = requestAnimationFrame(loop);

        if (p.cpu) {
          setTimeout(stopSpin, this.fast ? 150 : rand(500, 1100));
        }
      };

      const stopSpin = async () => {
        if (!this.spinning) return;
        this.spinning = false;
        cancelAnimationFrame(this.rafId);
        this.el.spinBtn.disabled = true;

        // いま針の下にある数字に、きっちり合わせて止める
        const n = this.numberAt(this.wheelAngle);
        const want = (360 - ((n - 1) * 36 + 18)) % 360;
        let delta = ((want - this.wheelAngle) % 360 + 360) % 360;
        if (delta > 180) delta -= 360;
        const from = this.wheelAngle;
        const dur = this.fast ? 60 : 260;
        const t0 = performance.now();
        await new Promise((res) => {
          const ease = (k) => 1 - Math.pow(1 - k, 3);
          const tick = () => {
            const k = Math.min(1, (performance.now() - t0) / dur);
            this.setWheel(from + delta * ease(k));
            if (k < 1) requestAnimationFrame(tick);
            else res();
          };
          requestAnimationFrame(tick);
        });
        this.el.wheelNum.textContent = n;
        this.el.spinBtn.textContent = `${n}!`;
        await this.wait(this.fast ? 80 : 320);
        resolve(n);
      };

      this.el.spinBtn.onclick = () => {
        if (this.spinning) stopSpin();
        else startSpin();
      };

      if (p.cpu) startSpin();
    });
  },

  /* ---------- メッセージ・選択肢 ---------- */

  show(which) {
    this.el.rouArea.classList.toggle("hidden", which !== "roulette");
    this.el.msgBox.classList.toggle("hidden", which !== "msg");
    this.el.choices.classList.toggle("hidden", which !== "choices");
  },

  say(p, text) {
    this.show("msg");
    this.el.msgText.innerHTML = String(text).replace(/\n/g, "<br>");
    this.el.msgBox.classList.toggle("auto", !!p.cpu);
    this.log(text.replace(/\n/g, " "), "msg");

    if (p.cpu) return this.wait(this.fast ? 120 : 900);
    return new Promise((resolve) => {
      this.el.msgBox.onclick = () => { this.el.msgBox.onclick = null; resolve(); };
    });
  },

  ask(p, question, labels) {
    this.show("choices");
    this.el.choices.innerHTML = "";
    const q = document.createElement("p");
    q.className = "choice-q";
    q.textContent = question;
    this.el.choices.appendChild(q);

    return new Promise((resolve) => {
      labels.forEach((label, i) => {
        const b = document.createElement("button");
        b.className = "choice-btn";
        b.textContent = label;
        b.onclick = () => { this.show("msg"); resolve(i); };
        this.el.choices.appendChild(b);
      });
    });
  },

  step(p) {
    Board.highlight = p.pos;
    this.el.hudCell.textContent = `いるマス:${BOARD[p.pos].e} ${BOARD[p.pos].n}`;
    return Board.animateToken(p, p.cpu && this.fast ? 0 : 150);
  },

  wait(ms) {
    return new Promise((r) => setTimeout(r, ms));
  },

  log(text, cls) {
    const div = document.createElement("div");
    div.className = `log-line ${cls || ""}`;
    div.textContent = text;
    this.el.log.appendChild(div);
    while (this.el.log.children.length > 60) this.el.log.removeChild(this.el.log.firstChild);
    this.el.log.scrollTop = this.el.log.scrollHeight;
  },

  /* ---------- パネル ---------- */

  /* 株は見込み(1株200万)で計算した暫定順位。誰が勝っているかを常に見せる。 */
  provisional(p) {
    const family = (p.spouse ? 1 : 0) + p.kids;
    const cash = p.cash >= 0 ? p.cash : Math.round(p.cash * DEBT_RATE);
    return cash + p.house + p.stocks.length * 200 + family * FAMILY_BONUS;
  },

  refresh() {
    const st = Game.state;
    const cur = Game.cur();
    this.el.hudTurn.innerHTML = st.over
      ? "清算中……"
      : `${st.turn}巡目 / <span class="turn-name" style="color:${cur.color}">${cur.emoji} ${cur.name}</span> の番`;
    if (!st.over) this.el.hudCell.textContent = `いるマス:${BOARD[cur.pos].e} ${BOARD[cur.pos].n}`;

    const ordered = [...Game.players()].sort((a, b) => this.provisional(b) - this.provisional(a));
    this.el.players.innerHTML = "";
    ordered.forEach((p, i) => {
      const card = document.createElement("div");
      card.className = "pcard" + (p === Game.cur() && !st.over ? " cur" : "") + (p.goaled ? " goaled" : "");
      card.style.borderColor = p.color;
      const family = (p.spouse ? 1 : 0) + p.kids;
      const tags = [
        p.house ? "🏠" : "",
        p.stocks.length ? `📈${p.stocks.length}` : "",
        p.insured ? "🛡" : "",
        family ? `👪${family}` : "",
        p.goaled ? `🏰${p.goalRank + 1}着` : "",
      ].filter(Boolean).join(" ");
      card.innerHTML = `
        <div class="pcard-top">
          <span class="prank">${i + 1}位</span>
          <span class="pname" style="color:${p.color}">${p.emoji} ${p.name}</span>
          <span class="pcpu">${p.cpu ? CPU_STYLE[p.cpu] : "あなた"}</span>
        </div>
        <div class="pcard-money ${p.cash < 0 ? "debt" : ""}">${p.cash < 0 ? `借金 ${yen(-p.cash)}` : yen(p.cash)}</div>
        <div class="pcard-sub">
          ${p.job ? `${p.job.emoji}${p.job.name} 給料${yen(p.salary)}` : "職業まだなし"}
        </div>
        <div class="pcard-tags">${tags || "&nbsp;"}</div>
        <div class="pcard-prov">暫定資産 ${yen(this.provisional(p))}<small>(株は見込み)</small></div>
      `;
      this.el.players.appendChild(card);
    });
  },

  /* ---------- 進行 ---------- */

  async start(count) {
    Game.newGame(this.el.nameInput.value.trim(), count);
    this.el.title.classList.add("hidden");
    this.el.game.classList.remove("hidden");
    Board.init();
    this.refresh();
    this.log("── 人生モドキ、はじまります ──", "head");
    await this.loop();
  },

  async loop() {
    const st = Game.state;
    while (!st.over) {
      const p = Game.cur();
      Board.highlight = p.pos;
      this.refresh();
      if (!p.cpu) this.log(`▼ あなたの番です`, "head");
      await Game.playTurn(p);
      if (Game.allGoaled()) break;
      Game.advance();
    }
    await this.finish();
  },

  async finish() {
    Game.state.over = true;
    this.refresh();
    this.show("msg");
    await this.say(Game.players()[0], "全員 ゴールした。\n株券を 清算して、総資産で 順位を きめる。");

    const ranked = Game.settleAll();
    this.el.game.classList.add("hidden");
    this.el.result.classList.remove("hidden");

    this.el.resultBody.innerHTML = "";
    ranked.forEach((p, i) => {
      const rank = RANK_TITLES[Math.min(i, RANK_TITLES.length - 1)];
      const box = document.createElement("div");
      box.className = "rbox" + (i === 0 ? " win" : "");
      box.style.borderColor = p.color;
      const lines = p.settle.lines.map((l) => `
        <tr>
          <th>${l.label}</th>
          <td class="${l.value < 0 ? "minus" : "plus"}">${yen(l.value)}</td>
        </tr>
        ${l.note ? `<tr class="note"><td colspan="2">${l.note}</td></tr>` : ""}
      `).join("");
      box.innerHTML = `
        <div class="rhead">
          <span class="rrank">${i + 1}位</span>
          <span class="rname" style="color:${p.color}">${p.emoji} ${p.name}</span>
          <span class="rtotal">${yen(p.settle.total)}</span>
        </div>
        <div class="rtitle">${rank.e} ${rank.title}</div>
        <p class="rtext">${rank.text}</p>
        <table class="rtable">${lines}</table>
        <p class="rroute">歩いた道:${p.route.length ? p.route.join(" → ") : "気づいたら ゴールしていた"}
          / ${p.job ? `職業:${p.job.name}` : "職業:なし"} / ${p.goalRank + 1}着でゴール</p>
      `;
      this.el.resultBody.appendChild(box);
    });
  },
};

window.addEventListener("DOMContentLoaded", () => UI.init());
