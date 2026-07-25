/* =========================================================
 * 人生モドキ ゲームロジック
 * ボード生成・ルーレット結果の処理・マス効果・CPU思考・清算
 *
 * 画面表示は UI 側の以下だけに頼る(差し替え可能):
 *   UI.spin(p)              -> Promise<1..10>
 *   UI.say(p, text)         -> Promise<void>
 *   UI.ask(p, q, labels)    -> Promise<index>
 *   UI.step(p)              -> Promise<void>   コマを1マス動かす演出
 *   UI.log(text, cls)       -> void
 *   UI.refresh()            -> void
 * =======================================================*/

/* ---------- ボード生成 ---------- */

function buildBoard() {
  const cells = [];
  const bands = [];

  for (const band of BOARD_BANDS) {
    const subs = band.split ? [band.up, band.low] : [band];
    bands.push(subs.map((sub) => {
      const start = cells.length;
      sub.cells.forEach((def, i) => {
        cells.push({
          ...def,
          idx: cells.length,
          col: sub.col0 + sub.dir * i,
          row: sub.row,
          next: [],
        });
      });
      for (let i = start; i < cells.length - 1; i++) cells[i].next = [{ to: i + 1 }];
      return { start, end: cells.length - 1, label: sub.label };
    }));
  }

  // バンドの終端 → 次のバンドの各先頭。next が2本になったマスが分岐マス。
  for (let b = 0; b < bands.length - 1; b++) {
    for (const sub of bands[b]) {
      cells[sub.end].next = bands[b + 1].map((ns) => ({ to: ns.start, label: ns.label }));
    }
  }
  return cells;
}

const BOARD = buildBoard();
const GOAL_IDX = BOARD.findIndex((c) => c.k === "goal");

/* 1マス戻る用。合流地点では最初に見つかった道を採用する。 */
function prevOf(idx) {
  for (const c of BOARD) {
    if (c.next.some((n) => n.to === idx)) return c.idx;
  }
  return idx;
}

/* ---------- ユーティリティ ---------- */

function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(arr) {
  return arr[rand(0, arr.length - 1)];
}

function weighted(table) {
  const total = table.reduce((s, x) => s + x.w, 0);
  let r = Math.random() * total;
  for (const x of table) {
    r -= x.w;
    if (r < 0) return x;
  }
  return table[table.length - 1];
}

function yen(n) {
  return `${n < 0 ? "-" : ""}${Math.abs(n).toLocaleString("ja-JP")}万円`;
}

/* =========================================================
 * Game
 * =======================================================*/

const Game = {
  state: null,

  newGame(playerName, count) {
    const players = PLAYER_SLOTS.slice(0, count).map((slot, i) => ({
      id: i,
      name: i === 0 ? (playerName || "あなた") : slot.name,
      emoji: slot.emoji,
      color: slot.color,
      cpu: slot.cpu,
      pos: 0,
      cash: START_CASH,
      job: null,
      salary: 0,
      stocks: [],        // 買値の配列
      house: 0,          // 家の評価額(0なら未所有)
      insured: false,
      insuranceUsed: false,
      spouse: false,
      kids: 0,
      goaled: false,
      goalRank: -1,      // 0始まり
      familyBonusPlus: 0, // 教育投資などで上がる家族1人あたりのボーナス
      route: [],         // 通ったルート名(結果画面用)
      settle: null,
    }));
    this.state = { players, turn: 1, cur: 0, goalCount: 0, over: false };
  },

  players() { return this.state.players; },
  cur() { return this.state.players[this.state.cur]; },
  allGoaled() { return this.state.players.every((p) => p.goaled); },

  /* 次の未ゴールプレイヤーへ。全員1周したらターン数+1。 */
  advance() {
    const st = this.state;
    for (let i = 0; i < st.players.length; i++) {
      st.cur = (st.cur + 1) % st.players.length;
      if (st.cur === 0) st.turn++;
      if (!st.players[st.cur].goaled) return;
    }
    st.over = true;
  },

  /* ---------- お金 ---------- */

  /* 支払いで足りなければ約束手形(=現金がマイナスになる)。 */
  pay(p, amount, why) {
    p.cash -= amount;
    UI.log(`${p.emoji} ${p.name}:${why} ${yen(-amount)}`, amount > 0 ? "minus" : "plus");
    if (UI.sfx) UI.sfx(amount > 0 ? "pay" : "coin");
    UI.refresh();
  },

  gain(p, amount, why) {
    this.pay(p, -amount, why);
  },

  payday(p, passing) {
    const salary = p.salary || 100;   // 無職ならバイト代
    p.cash += salary;
    UI.log(`${p.emoji} ${p.name}:給料日${passing ? "を通過" : ""} +${yen(salary)}`, "plus");
    if (UI.jingle && !passing) UI.jingle("payday");
    else if (UI.sfx) UI.sfx("coin");
    UI.refresh();
  },

  /* ---------- 移動 ---------- */

  async move(p, steps) {
    if (steps < 0) {
      for (let i = 0; i < -steps && p.pos > 0; i++) {
        p.pos = prevOf(p.pos);
        await UI.step(p);
      }
      return;
    }
    for (let i = 0; i < steps; i++) {
      const nexts = BOARD[p.pos].next;
      if (!nexts.length) break;

      let to = nexts[0].to;
      if (nexts.length > 1) {
        const labels = nexts.map((n) => n.label);
        const choice = p.cpu
          ? Cpu.chooseRoute(p, labels)
          : await UI.ask(p, "どっちの人生へ すすむ?", labels);
        to = nexts[choice].to;
        p.route.push(labels[choice]);
        await UI.say(p, `${p.name}は「${labels[choice]}」を えらんだ。`);
      }

      p.pos = to;
      await UI.step(p);

      const cell = BOARD[to];
      if (cell.k === "goal") break;                 // ゴールは行きすぎない
      if (cell.stop) break;                         // 就職・結婚は必ず止まる
      if (i < steps - 1) await this.passCell(p, cell);
    }
  },

  /* 通過するだけで効果が出るマス(給料日と、学費のような避けられない出費) */
  async passCell(p, cell) {
    if (cell.k === "payday") { this.payday(p, true); return; }
    if (!cell.always) return;
    if (cell.m) this.pay(p, -cell.m, `${cell.n}(通過)`);
    if (cell.salary) p.salary += cell.salary;
    await UI.say(p, `【${cell.n}】通りかかっただけでも、これは 避けられない。\n${cell.t || ""}`);
  },

  /* ---------- 1ターン ---------- */

  async playTurn(p) {
    const n = await UI.spin(p);
    UI.log(`── ${p.emoji} ${p.name} は ${n} を 出した`, "head");
    await this.move(p, n);
    await this.resolve(p, 0);
  },

  /* 止まったマスの効果。mv マスからの連鎖は2回までで打ち切る。 */
  async resolve(p, depth) {
    const cell = BOARD[p.pos];
    UI.refresh();
    if (cell.t) await UI.say(p, `【${cell.n}】\n${cell.t}`);
    else await UI.say(p, `【${cell.n}】`);

    switch (cell.k) {
      case "money": {
        if (cell.m) this.pay(p, -cell.m, cell.n);
        if (cell.salary) {
          p.salary += cell.salary;
          UI.log(`${p.emoji} ${p.name}:給料が +${yen(cell.salary)} になった`, "plus");
        }
        break;
      }

      case "payday":
        this.payday(p, false);
        break;

      /* 二択マス。安全な一手と、勝負手。 */
      case "choice": {
        const labels = cell.opts.map((o) => o.label);
        const i = p.cpu
          ? Cpu.chooseOption(p, cell)
          : await UI.ask(p, cell.q || "どうする?", labels);
        const o = cell.opts[i];
        UI.log(`${p.emoji} ${p.name}:${cell.n} →「${o.label}」`, "head");
        if (o.m) this.pay(p, -o.m, cell.n);
        if (o.salary) {
          p.salary += o.salary;
          UI.log(`${p.emoji} ${p.name}:給料が +${yen(o.salary)} になった`, "plus");
        }
        if (o.familyBonus) p.familyBonusPlus += o.familyBonus;

        let text = o.t || "";
        if (o.risk) {
          const hit = Math.random() < o.risk.p;
          const amount = hit ? o.risk.win : o.risk.lose;
          if (amount) this.pay(p, -amount, cell.n);
          text += `\n${hit ? o.risk.winText : o.risk.loseText}(${yen(amount)})`;
        }
        await UI.say(p, text);
        break;
      }

      case "job": {
        const job = pick(JOBS[cell.jobs]);
        if (UI.scene) await UI.scene("job", { color: p.color });
        p.job = job;
        p.salary = job.salary;
        await UI.say(p, `${p.name}の職業は「${job.emoji} ${job.name}」に きまった。\n給料は 1回 ${yen(job.salary)}。`);
        break;
      }

      case "jobchange": {
        const pool = JOBS[p.job && JOBS.uni.includes(p.job) ? "uni" : "work"];
        const yes = p.cpu
          ? Cpu.decide(p, "jobchange")
          : (await UI.ask(p, `いまは ${p.job ? p.job.name : "無職"}(給料 ${yen(p.salary)})。転職する?`,
              ["転職する(給料は 運まかせ)", "いまのままで いい"])) === 0;
        if (!yes) { await UI.say(p, "求人票を 閉じた。それも 勇気だ。"); break; }
        const job = pick(pool.filter((j) => j !== p.job));
        const before = p.salary;
        p.job = job;
        p.salary = job.salary;
        await UI.say(p, `「${job.emoji} ${job.name}」に 転職した。\n給料 ${yen(before)} → ${yen(job.salary)}。` +
          (job.salary >= before ? "\nやったな。" : "\n……やってしまったな。"));
        break;
      }

      case "insurance": {
        if (p.insured) { await UI.say(p, "すでに 加入している。同じ話を 2回 聞いた。"); break; }
        const yes = p.cpu
          ? Cpu.decide(p, "insurance", cell)
          : (await UI.ask(p, `保険に 入る? 保険料 ${yen(cell.cost)}`,
              [`加入する(${yen(cell.cost)})`, "入らない"])) === 0;
        if (!yes) { await UI.say(p, "「また 今度」と 言って 帰した。"); break; }
        this.pay(p, cell.cost, "保険料");
        p.insured = true;
        await UI.say(p, "保険に 加入した。事故の支払いを 1回 肩代わりしてくれる。\n使わずに ゴールすれば 満期返戻金も もらえる。");
        break;
      }

      case "accident": {
        if (p.insured && !p.insuranceUsed) {
          p.insuranceUsed = true;
          p.insured = false;
          if (UI.scene) await UI.scene("saved", { color: p.color });
          await UI.say(p, `保険が おりた! 支払い ${yen(cell.m ? -cell.m : 0)} は ゼロ。\nあの日の勧誘を 断らなくて よかった。`);
        } else {
          if (UI.scene) await UI.scene("accident", { color: p.color });
          if (UI.shake) UI.shake();
          this.pay(p, -cell.m, "修理と治療");
        }
        break;
      }

      /* 火事。家がなければ他人事、保険があれば助かる。 */
      case "fire": {
        if (!p.house) {
          await UI.say(p, "近所で ぼや。うちは 賃貸なので 見物した。\n身軽であることの 数少ない 勝利。");
          break;
        }
        if (p.insured && !p.insuranceUsed) {
          p.insuranceUsed = true;
          p.insured = false;
          if (UI.scene) await UI.scene("saved", { color: p.color });
          await UI.say(p, `火は 出たが、保険が 全額 出た。\n修理代 ${yen(-cell.m)} は ゼロ。`);
        } else {
          if (UI.scene) await UI.scene("fire", { color: p.color });
          if (UI.shake) UI.shake();
          this.pay(p, -cell.m, "火事の修理");
          await UI.say(p, "家は 直せる。写真は 戻らない。\n保険の 勧誘を 思い出していた。");
        }
        break;
      }

      /* 宝くじ。清算はゴール後、1枚ごとに抽選。 */
      case "lottery": {
        const yes = p.cpu
          ? Cpu.decide(p, "lottery", cell)
          : (await UI.ask(p, `宝くじを 1枚 買う? ${yen(cell.price)}(1等 1200万・確率8%)`,
              [`買う(${yen(cell.price)})`, "夢を 見ない"])) === 0;
        if (!yes) { await UI.say(p, "堅実。だが 夢も ない。"); break; }
        this.pay(p, cell.price, "宝くじ");
        p.lottery = (p.lottery || 0) + 1;
        await UI.say(p, `宝くじを 買った(${p.lottery}枚目)。\n抽選日は ゴールの日だ。`);
        break;
      }

      /* ハプニング。デッキからランダムで1つ引く。 */
      case "happen": {
        const ev = pick(HAPPENINGS);
        if (UI.scene) await UI.scene("happen", { color: p.color });
        UI.log(`${p.emoji} ${p.name}:${ev.e} ${ev.n}`, "head");
        await UI.say(p, `${ev.e}【${ev.n}】\n${ev.t}`);
        if (ev.m) this.pay(p, -ev.m, ev.n);
        if (ev.mv && depth < 2) {
          await this.move(p, ev.mv);
          await this.resolve(p, depth + 1);
          return;
        }
        break;
      }

      case "stock": {
        const yes = p.cpu
          ? Cpu.decide(p, "stock", cell)
          : (await UI.ask(p, `株を 1株 買う? 1株 ${yen(cell.price)}(ゴール時に 清算)`,
              [`買う(${yen(cell.price)})`, "買わない"])) === 0;
        if (!yes) { await UI.say(p, "手を出さなかった。堅実だ。たぶん。"); break; }
        this.pay(p, cell.price, "株の購入");
        p.stocks.push(cell.price);
        await UI.say(p, `株券を 1枚 手に入れた(いま ${p.stocks.length}枚)。\n価値が わかるのは ゴールしてから。`);
        break;
      }

      case "gamble": {
        const yes = p.cpu
          ? Cpu.decide(p, "gamble", cell)
          : (await UI.ask(p, `${yen(cell.bet)} 賭ける? 当たれば 2.2倍(当たる確率 45%)`,
              [`賭ける(${yen(cell.bet)})`, "見送る"])) === 0;
        if (!yes) { await UI.say(p, "見送った。賢い。おもしろくないが 賢い。"); break; }
        this.pay(p, cell.bet, "賭け金");
        if (Math.random() < 0.45) {
          const win = Math.round(cell.bet * 2.2);
          if (UI.scene) await UI.scene("win", { color: p.color });
          this.gain(p, win, "的中");
          await UI.say(p, `当たった! ${yen(win)} が ころがり込んだ。\nこの成功体験が、後で 効いてくる。悪い意味で。`);
        } else {
          if (UI.scene) await UI.scene("lose", { color: p.color });
          await UI.say(p, `外れた。${yen(cell.bet)} は 消えた。\n「次は 当たる」と 思っている顔だ。`);
        }
        break;
      }

      case "house": {
        if (p.house) { await UI.say(p, "もう 家は ある。2軒目は さすがに 無理。"); break; }
        const yes = p.cpu
          ? Cpu.decide(p, "house", cell)
          : (await UI.ask(p, `家を 買う? ${yen(cell.cost)}(ゴール時 評価額 ${yen(cell.value)})`,
              [`買う(${yen(cell.cost)})`, "賃貸で いく"])) === 0;
        if (!yes) { await UI.say(p, "賃貸で いくことにした。身軽が いちばん。"); break; }
        if (UI.scene) await UI.scene("house", { color: p.color });
        this.pay(p, cell.cost, "住宅購入");
        p.house = cell.value;
        await UI.say(p, `マイホームを 手に入れた!\n買値 ${yen(cell.cost)} / 評価額 ${yen(cell.value)}。差額は 思い出の代金。`);
        break;
      }

      case "marry": {
        if (UI.scene) await UI.scene("marry", { color: p.color });
        this.pay(p, cell.cost, "結婚式");
        p.spouse = true;
        const gift = rand(2, 8) * 60;
        this.gain(p, gift, "ご祝儀");
        await UI.say(p, `結婚した! ご祝儀は ${yen(gift)}。\n家族が 1人 ふえた(ゴール時 +${yen(FAMILY_BONUS)})。`);
        break;
      }

      case "baby": {
        const twins = rand(1, 10) === 1;
        const num = twins ? 2 : 1;
        if (UI.scene) await UI.scene("baby", { color: p.color, count: num });
        p.kids += num;
        this.pay(p, 50 * num, "出産費用");
        await UI.say(p, twins
          ? `双子が うまれた! 家族が 2人 ふえた。\n夜は もう 来ないものと 思ってほしい。`
          : `子どもが うまれた。家族が 1人 ふえた(ゴール時 +${yen(FAMILY_BONUS)})。`);
        break;
      }

      case "collect": {
        const others = this.players().filter((o) => o !== p);
        for (const o of others) o.cash -= cell.m;
        p.cash += cell.m * others.length;
        UI.log(`${p.emoji} ${p.name}:全員から ${yen(cell.m)} ずつ 徴収(+${yen(cell.m * others.length)})`, "plus");
        UI.refresh();
        await UI.say(p, `${others.map((o) => o.name).join("・")} から ${yen(cell.m)} ずつ もらった。`);
        break;
      }

      case "pay": {
        const others = this.players().filter((o) => o !== p);
        for (const o of others) o.cash += cell.m;
        p.cash -= cell.m * others.length;
        UI.log(`${p.emoji} ${p.name}:全員へ ${yen(cell.m)} ずつ 支払い(${yen(-cell.m * others.length)})`, "minus");
        UI.refresh();
        await UI.say(p, `${others.map((o) => o.name).join("・")} に ${yen(cell.m)} ずつ 配った。喜ばれた。`);
        break;
      }

      case "move": {
        if (depth >= 2) { await UI.say(p, "……いや、もう 動かない。疲れた。"); break; }
        await this.move(p, cell.mv);
        await this.resolve(p, depth + 1);
        return;
      }

      case "goal":
        await this.reachGoal(p);
        return;

      default:
        break;
    }

    if (p.cash < 0) {
      await UI.say(p, `お金が たりない。約束手形を きった。\n借金 ${yen(-p.cash)}(ゴール時に ${DEBT_RATE}倍で 清算)。`);
    }
    UI.refresh();
  },

  /* ---------- ゴールと清算 ---------- */

  async reachGoal(p) {
    p.goaled = true;
    p.goalRank = this.state.goalCount++;
    if (UI.scene) await UI.scene("goal", { color: p.color });
    const bonus = GOAL_BONUS[Math.min(p.goalRank, GOAL_BONUS.length - 1)];
    p.cash += bonus;
    UI.log(`🏰 ${p.name} が ${p.goalRank + 1}着で ゴール! 賞金 +${yen(bonus)}`, "head");
    if (UI.celebrate) UI.celebrate(p);   // 城から紙吹雪(シミュレータのスタブUIには無い)
    UI.refresh();
    await UI.say(p, `${p.name}、${p.goalRank + 1}着で ゴール!\nゴール賞金 ${yen(bonus)}。\n株の清算は 全員が ゴールしてから。`);
  },

  /* 総資産を確定させる。呼ぶのは全員ゴール後。 */
  settleAll() {
    for (const p of this.players()) {
      const lines = [];
      let total = 0;

      const cash = p.cash;
      if (cash >= 0) {
        lines.push({ label: "手持ちの現金", value: cash });
        total += cash;
      } else {
        const debt = Math.round(-cash * DEBT_RATE);
        lines.push({ label: `借金の清算(利息${DEBT_RATE}倍)`, value: -debt });
        total -= debt;
      }

      if (p.house) {
        lines.push({ label: "家の評価額", value: p.house });
        total += p.house;
      }

      p.stockResults = p.stocks.map(() => weighted(STOCK_PAYOUTS));
      if (p.stocks.length) {
        const sum = p.stockResults.reduce((s, r) => s + r.pay, 0);
        lines.push({
          label: `株券 ${p.stocks.length}枚の清算`,
          value: sum,
          note: p.stockResults.map((r) => r.text).join(" / "),
        });
        total += sum;
      }

      const family = (p.spouse ? 1 : 0) + p.kids;
      if (family) {
        const per = FAMILY_BONUS + p.familyBonusPlus;
        lines.push({
          label: `家族 ${family}人のボーナス(1人 ${yen(per)})`,
          value: family * per,
        });
        total += family * per;
      }

      if (p.lottery) {
        let winSum = 0;
        for (let i = 0; i < p.lottery; i++) if (Math.random() < 0.08) winSum += 1200;
        lines.push({
          label: `宝くじ ${p.lottery}枚の抽選`,
          value: winSum,
          note: winSum > 0 ? "1等が 当たってしまった。人生とは。" : "夢は 50万円だった。",
        });
        total += winSum;
      }

      if (p.insured && !p.insuranceUsed) {
        lines.push({ label: "保険の満期返戻金", value: INSURANCE_REFUND });
        total += INSURANCE_REFUND;
      }

      p.settle = { lines, total };
    }

    return [...this.players()].sort((a, b) => b.settle.total - a.settle.total);
  },
};

/* =========================================================
 * CPU の思考
 *   bold   何にでも手を出す / safe とにかく守る / greedy 出したがらない
 * =======================================================*/

const Cpu = {
  /* 分岐。labels[0] が遠回り側。 */
  chooseRoute(p, labels) {
    if (labels.length < 2) return 0;
    if (p.cpu === "bold") return 0;                  // 遠回りでも高給・家族ボーナスを狙う
    if (p.cpu === "safe") return p.cash > 800 ? 0 : 1;
    return 1;                                        // greedy は近道で現金を抱えて逃げる
  },

  /* 二択マス。bold は勝負手、safe は安全手、greedy は出費のすくない手。 */
  chooseOption(p, cell) {
    const opts = cell.opts;
    const cost = (o) => -(o.m || 0) + (o.risk ? Math.max(0, -o.risk.lose) : 0);
    const riskIdx = opts.findIndex((o) => o.risk);

    if (p.cpu === "bold" && riskIdx >= 0) return riskIdx;
    if (p.cpu === "greedy") {
      let best = 0;
      opts.forEach((o, i) => { if (cost(o) < cost(opts[best])) best = i; });
      return best;
    }
    // safe / 手持ちが心もとない bold は、賭けない手を選ぶ
    const plain = opts.findIndex((o) => !o.risk && cost(o) <= Math.max(0, p.cash));
    return plain >= 0 ? plain : 0;
  },

  /* 買う/賭ける/転職するなら true */
  decide(p, kind, cell) {
    switch (kind) {
      case "insurance":
        if (p.cash < cell.cost) return false;
        return p.cpu === "safe" || (p.cpu === "bold" && p.cash > 1200);

      case "stock":
        if (p.cash < cell.price) return false;
        if (p.cpu === "bold") return true;
        if (p.cpu === "safe") return p.cash > cell.price * 4;
        return false;

      case "gamble":
        if (p.cash < cell.bet) return false;
        if (p.cpu === "bold") return true;
        if (p.cpu === "safe") return this.isLosing(p) && p.cash > cell.bet * 3;
        return false;

      case "house":
        if (p.cash < cell.cost * 0.6) return false;  // 少しの借金なら家は買う
        return p.cpu !== "greedy";

      case "jobchange":
        if (p.cpu === "bold") return true;
        return p.salary < 400;                       // 給料が低いときだけ動く

      case "lottery":
        if (p.cash < cell.price) return false;
        // 守銭奴ほど宝くじは買う。人間とは そういうものだ
        return p.cpu === "greedy" || p.cpu === "bold";

      default:
        return false;
    }
  },

  /* 負けているCPUは勝負に出る(逆転を狙う) */
  isLosing(p) {
    const best = Math.max(...Game.players().map((o) => o.cash));
    return p.cash < best * 0.7;
  },
};
