/* =========================================================
 * ときめきモドキ ゲームロジック
 * 状態管理・ターン進行・爆弾・エンディング判定
 * =======================================================*/

const MAX_TURN = 36;
const CONFESS_AFF = 80;       // 告白(個別エンド)に必要な好感度
const BOMB_IDLE_TURNS = 6;    // 放置で爆弾が出現するターン数
const BOMB_FUSE = 3;          // 出現から爆発までのターン数

const Game = {
  state: null,

  newGame(name) {
    const chars = {};
    for (const c of CHARACTERS) {
      chars[c.id] = {
        aff: 5,
        lastTalk: 0,
        bomb: 0,        // 0=なし / 残りターン数
        met: false,
        seen40: false,
        seen70: false,
        dateIdx: 0,
      };
    }
    this.state = {
      name,
      turn: 1,
      stats: { study: 20, sport: 20, looks: 20, trivia: 20, stress: 0 },
      chars,
      over: false,
      endingKey: null,
    };
  },

  rand(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  },

  charById(id) {
    return CHARACTERS.find((c) => c.id === id);
  },

  addStat(key, n) {
    const s = this.state.stats;
    s[key] = Math.max(0, Math.min(100, s[key] + n));
  },

  addAff(id, n) {
    const ch = this.state.chars[id];
    ch.aff = Math.max(0, Math.min(100, ch.aff + n));
    if (n >= 5) {
      // ちゃんと構ったとみなして爆弾タイマーをリセット
      ch.lastTalk = this.state.turn;
      ch.bomb = 0;
    }
  },

  /* 選択肢の効果を適用し、結果メッセージと数値変化の表示用文字列を返す */
  applyEffect(eff, ctxCharId) {
    const deltas = [];
    if (eff.stats) {
      for (const [k, v] of Object.entries(eff.stats)) {
        this.addStat(k, v);
        deltas.push(`${STAT_NAMES[k]}${v > 0 ? "+" : ""}${v}`);
      }
    }
    if (eff.self && ctxCharId) {
      this.addAff(ctxCharId, eff.self);
      deltas.push(`${this.charById(ctxCharId).name}の好感度+${eff.self}`);
    }
    if (eff.aff) {
      for (const [id, v] of Object.entries(eff.aff)) {
        this.addAff(id, v);
        deltas.push(`${this.charById(id).name}の好感度${v > 0 ? "+" : ""}${v}`);
      }
    }
    if (eff.all) {
      for (const c of CHARACTERS) this.addAff(c.id, eff.all);
      deltas.push(`全員の好感度+${eff.all}`);
    }
    return { msg: eff.msg, deltas };
  },

  /* 選択肢を解決(ステータスチェック分岐込み) */
  resolveChoice(choice, ctxCharId) {
    if (choice.check) {
      const ok = this.state.stats[choice.check.stat] >= choice.check.min;
      return this.applyEffect(ok ? choice.check.ok : choice.check.ng, ctxCharId);
    }
    return this.applyEffect(choice.effect, ctxCharId);
  },

  /* コマンド実行。ログとイベントキューを返す */
  processCommand(cmd, dateCharId) {
    const s = this.state;
    const logs = [];
    const events = [];

    if (cmd === "date") {
      const ch = s.chars[dateCharId];
      const def = this.charById(dateCharId);
      // 好きなステータスが高いほどデートが効く(基礎ボーナス)
      const bonus = Math.floor(s.stats[def.favStat] / 25);
      ch.aff = Math.min(100, ch.aff + bonus);
      ch.lastTalk = s.turn;
      ch.bomb = 0;
      const pool = DATE_EVENTS[dateCharId];
      const ev = pool[ch.dateIdx % pool.length];
      ch.dateIdx++;
      logs.push(`${def.name}を遊びに誘った。`);
      events.push({ charId: dateCharId, ...ev });
    } else {
      const def = COMMANDS[cmd];
      for (const [k, range] of Object.entries(def.gain)) {
        this.addStat(k, this.rand(range[0], range[1]));
      }
      this.addStat("stress", def.stress);
      logs.push(def.flavor[this.rand(0, def.flavor.length - 1)]);
      if (Math.random() < 0.2) {
        logs.push(RANDOM_LINES[this.rand(0, RANDOM_LINES.length - 1)]);
      }
    }

    // 出会いイベント(1〜3ターン目)
    const intro = INTRO_EVENTS[s.turn];
    if (intro) {
      s.chars[intro.charId].met = true;
      s.chars[intro.charId].lastTalk = s.turn;
      events.push(intro);
    }

    // 学校行事
    if (FIXED_EVENTS[s.turn]) {
      events.push({ charId: null, ...FIXED_EVENTS[s.turn] });
    }

    return { logs, events };
  },

  /* 好感度しきい値イベントのチェック(イベント解決のたびに呼ぶ) */
  checkThresholds() {
    const events = [];
    for (const c of CHARACTERS) {
      const ch = this.state.chars[c.id];
      if (!ch.met) continue;
      if (!ch.seen40 && ch.aff >= 40) {
        ch.seen40 = true;
        events.push({ charId: c.id, ...THRESHOLD_EVENTS[c.id][40] });
      } else if (!ch.seen70 && ch.aff >= 70) {
        ch.seen70 = true;
        events.push({ charId: c.id, ...THRESHOLD_EVENTS[c.id][70] });
      }
    }
    return events;
  },

  /* ターン終了処理:爆弾・進級・終了判定 */
  endTurn() {
    const s = this.state;
    const logs = [];

    // ---- 爆弾システム(パロディ) ----
    for (const c of CHARACTERS) {
      const ch = s.chars[c.id];
      if (!ch.met) continue;

      if (ch.bomb > 0) {
        ch.bomb--;
        if (ch.bomb === 0) {
          // しおりの好感度が高ければ、趣味で解除してくれる(本人の爆弾は除く)
          if (c.id !== "shiori" && s.chars.shiori.aff >= 60 && Math.random() < 0.7) {
            logs.push({ text: BOMB_TEXT.defuse(c.name), cls: "log-sys" });
            ch.lastTalk = s.turn;
          } else {
            logs.push({ text: BOMB_TEXT.explode(c.name), cls: "log-warn" });
            if (c.id === "shiori") {
              logs.push({ text: BOMB_TEXT.selfBombNote, cls: "log-sys" });
            }
            this.addStat("stress", 8);
            ch.aff = Math.max(0, ch.aff - 15);
            for (const o of CHARACTERS) {
              if (o.id !== c.id) s.chars[o.id].aff = Math.max(0, s.chars[o.id].aff - 5);
            }
            ch.lastTalk = s.turn;
          }
        } else {
          logs.push({ text: BOMB_TEXT.countdown(c.name, ch.bomb), cls: "log-warn" });
        }
      } else if (ch.aff >= 15 && s.turn - ch.lastTalk >= BOMB_IDLE_TURNS) {
        ch.bomb = BOMB_FUSE;
        logs.push({ text: BOMB_TEXT.appear(c.name), cls: "log-warn" });
      }
    }

    // ---- ターンを進める ----
    s.turn++;

    if (YEAR_MESSAGES[s.turn]) {
      logs.push({ text: YEAR_MESSAGES[s.turn], cls: "log-sys" });
    }

    // ---- 終了判定 ----
    let endingKey = null;
    if (s.stats.stress >= 100) {
      endingKey = "bad";
    } else if (s.turn > MAX_TURN) {
      endingKey = this.decideEnding();
    }
    if (endingKey) {
      s.over = true;
      s.endingKey = endingKey;
    }

    return { logs, endingKey };
  },

  decideEnding() {
    const s = this.state;
    if (s.stats.stress >= 85) return "bad";

    const high = CHARACTERS.filter((c) => s.chars[c.id].aff >= CONFESS_AFF);
    if (high.length >= 2) return "harem";
    if (high.length === 1) return high[0].id;

    const maxAff = Math.max(...CHARACTERS.map((c) => s.chars[c.id].aff));
    if (maxAff >= 45) return "friend";
    return "tree";
  },

  /* 表示用:ターン → 「X年生 Y月」 */
  turnLabel(turn) {
    const t = Math.min(turn, MAX_TURN) - 1;
    const year = Math.floor(t / 12) + 1;
    const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
    return `${year}年生 ${months[t % 12]}月`;
  },
};
