/* =========================================================
 * モドキクエストII エンジン
 * 状態管理・移動・戦闘・セーブ(DOM非依存)
 * =======================================================*/

const SAVE_KEY = "modokiquest2_save";

function rnd(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function frnd(min, max) { return Math.random() * (max - min) + min; }

function statsFor(id, lv) {
  const gr = PARTY_DEFS[id].growth;
  const v = (pair) => Math.floor(pair[0] + pair[1] * lv);
  return { hp: v(gr.hp), mp: v(gr.mp), atk: v(gr.atk), def: v(gr.def), agi: v(gr.agi) };
}

function spellsFor(id, lv) {
  const at = PARTY_DEFS[id].spellsAt;
  const out = [];
  for (const [l, ids] of Object.entries(at)) {
    if (lv >= Number(l)) out.push(...ids);
  }
  return out;
}

function makeMember(id, lv) {
  const st = statsFor(id, lv);
  return {
    id, name: PARTY_DEFS[id].name,
    lv, exp: expForLevel(lv),
    hp: st.hp, mp: st.mp,
    weapon: null, armor: null, shield: null,
    defending: false, asleep: 0,
  };
}

const Game = {
  s: null,

  newGame() {
    this.s = {
      map: "castle1", x: 6, y: 5, dir: "down",
      party: [makeMember("ganba", 1)],
      gold: 0,
      items: {},          // 消耗品/だいじなもの {id: count}
      flags: {},
      opened: {},         // 宝箱 {id: true}
      ship: { has: false, x: 19, y: 18, on: false },
      steps: 0,
    };
  },

  /* ---------- マップ ---------- */

  mapDef() { return MAPS[this.s.map]; },
  tileAt(map, x, y) {
    const rows = MAPS[map].rows;
    if (y < 0 || y >= rows.length || x < 0 || x >= rows[0].length) return "#";
    return rows[y][x];
  },

  npcAt(x, y) {
    const list = this.mapDef().npcs || [];
    return list.find((n) => n.x === x && n.y === y && !this.npcGone(n));
  },
  npcGone(n) {
    // 加入・撃破済みNPCを消す
    if (n.event === "nonbi_join" && this.s.flags.nonbiJoined) return true;
    if (n.event === "cat_princess" && this.s.flags.myakoJoined) return true;
    if (n.event === "boss_tekkamen" && this.s.flags.crestNap) return true;
    if (n.event === "final_gate" && this.s.flags.gateOpen) return true;
    if (n.event === "boss_zannen" && this.s.flags.cleared) return true;
    return false;
  },

  chestAt(x, y) {
    const list = this.mapDef().chests || [];
    return list.find((c) => c.x === x && c.y === y);
  },

  /* 移動。結果: {moved} or {trigger:{...}} */
  move(dx, dy) {
    const s = this.s;
    s.dir = dy < 0 ? "up" : dy > 0 ? "down" : dx < 0 ? "left" : "right";
    const nx = s.x + dx, ny = s.y + dy;
    const t = this.tileAt(s.map, nx, ny);

    // NPC・宝箱はぶつかると会話/開封(QoL: はなすコマンド不要)
    const npc = this.npcAt(nx, ny);
    if (npc) return { trigger: { type: "npc", npc } };
    const chest = this.chestAt(nx, ny);
    if (chest && !s.opened[chest.id]) return { trigger: { type: "chest", chest } };

    // 船の乗り降り
    if (s.map === "world") {
      if (!s.ship.on && SAILABLE.has(t)) {
        if (s.ship.has && s.ship.x === nx && s.ship.y === ny) {
          s.ship.on = true; s.x = nx; s.y = ny;
          return { moved: true, boarded: true };
        }
        return {};
      }
      if (s.ship.on) {
        if (SAILABLE.has(t)) { s.x = nx; s.y = ny; return { moved: true }; }
        if (WALKABLE.has(t)) {
          s.ship.on = false; s.ship.x = s.x; s.ship.y = s.y;
          s.x = nx; s.y = ny;
          return this.afterStep(t);
        }
        return {};
      }
    }

    if (chest && s.opened[chest.id]) { /* 開封済みの箱は通れる */ }
    else if (!WALKABLE.has(t)) return {};

    s.x = nx; s.y = ny;
    return this.afterStep(t);
  },

  afterStep(t) {
    const s = this.s;
    s.steps++;

    // ポータル
    const links = this.mapDef().links || {};
    if (links[t]) {
      const L = links[t];
      return { moved: true, trigger: { type: "portal", to: L } };
    }
    if (t === "<") {
      const ex = this.mapDef().exit;
      return { moved: true, trigger: { type: "portal", to: { map: "world", x: ex.x, y: ex.y } } };
    }

    // エンカウント
    const def = this.mapDef();
    let zone = null;
    if (def.zone) zone = def.zone(s.x, s.y);
    else if (def.outdoor) zone = def.zone ? def.zone(s.x, s.y) : null;
    if (s.map === "world") zone = MAPS.world.zone(s.x, s.y);
    if (zone && !s.flags.cleared) {
      let rate = ENCOUNTER_RATE[zone] || 0;
      if (s.map === "world" && this.tileAt("world", s.x, s.y) === "f") rate *= 1.7; // 森は出やすい
      if (Math.random() < rate) {
        return { moved: true, trigger: { type: "encounter", enemies: this.rollEncounter(zone) } };
      }
    }
    return { moved: true };
  },

  transfer(to) {
    this.s.map = to.map; this.s.x = to.x; this.s.y = to.y;
    this.save(); // QoL: マップ移動でオートセーブ
  },

  rollEncounter(zone) {
    const table = ENCOUNTERS[zone];
    const pick = table[rnd(0, table.length - 1)];
    const ids = [];
    for (let i = 0; i < pick.length; i += 3) {
      const n = rnd(pick[i + 1], pick[i + 2]);
      for (let k = 0; k < n; k++) ids.push(pick[i]);
    }
    return ids;
  },

  /* ---------- パーティ ---------- */

  member(id) { return this.s.party.find((m) => m.id === id); },
  alive() { return this.s.party.filter((m) => m.hp > 0); },

  equipBonus(m, key) {
    let v = 0;
    for (const slot of ["weapon", "armor", "shield"]) {
      const e = m[slot] && EQUIP[m[slot]];
      if (e && e[key]) v += e[key];
    }
    return v;
  },
  atkOf(m) { return statsFor(m.id, m.lv).atk + this.equipBonus(m, "atk"); },
  defOf(m) { return statsFor(m.id, m.lv).def + this.equipBonus(m, "def"); },
  agiOf(m) { return statsFor(m.id, m.lv).agi; },
  maxHp(m) { return statsFor(m.id, m.lv).hp; },
  maxMp(m) { return statsFor(m.id, m.lv).mp; },

  join(id) {
    const lv = Math.max(this.s.party[0].lv - 1, id === "myako" ? 5 : 2);
    const m = makeMember(id, lv);
    if (id === "nonbi") m.weapon = "bat";
    if (id === "myako") m.weapon = "jarashi";
    this.s.party.push(m);
  },

  healAll() {
    for (const m of this.s.party) {
      m.hp = this.maxHp(m); m.mp = this.maxMp(m); m.asleep = 0;
    }
  },

  /* EXP獲得とレベルアップ。メッセージ配列を返す */
  gainExp(amount) {
    const msgs = [];
    for (const m of this.alive()) {
      m.exp += amount;
      while (m.lv < 20 && m.exp >= expForLevel(m.lv + 1)) {
        m.lv++;
        const before = spellsFor(m.id, m.lv - 1).length;
        const now = spellsFor(m.id, m.lv);
        msgs.push(`* ${m.name}は レベル${m.lv}に あがった!`);
        for (const sp of now.slice(before)) {
          msgs.push(`* ${m.name}は ${SPELLS[sp].name}を おぼえた!`);
        }
        m.hp = this.maxHp(m); m.mp = this.maxMp(m); // QoL: レベルアップで全回復
      }
    }
    return msgs;
  },

  spellsOf(m) { return spellsFor(m.id, m.lv); },

  /* 装備購入(QoL: 即装備・古いのは自動下取り) */
  buyEquip(eqId) {
    const eq = EQUIP[eqId];
    if (this.s.gold < eq.price) return { ok: false, msg: "* お金が たりない!" };
    const candidates = this.s.party.filter(
      (m) => eq.who.includes(m.id) && this.equipValue(m, eq.slot) < (eq.atk || eq.def)
    );
    if (!candidates.length) return { ok: false, msg: "* それを 役立てられる なかまは いない" };
    const m = candidates[0];
    let back = 0;
    if (m[eq.slot]) back = Math.floor(EQUIP[m[eq.slot]].price / 2);
    this.s.gold -= eq.price; this.s.gold += back;
    m[eq.slot] = eqId;
    const note = back ? `(ふるい そうびは ${back}Gで 下取り)` : "";
    return { ok: true, msg: `* ${m.name}は ${eq.name}を そうびした!${note}` };
  },
  equipValue(m, slot) {
    return m[slot] ? (EQUIP[m[slot]].atk || EQUIP[m[slot]].def) : 0;
  },

  /* 宝箱などからの装備入手 */
  gainEquip(eqId) {
    const eq = EQUIP[eqId];
    const m = this.s.party.find((mm) => eq.who.includes(mm.id));
    if (m && this.equipValue(m, eq.slot) < (eq.atk || eq.def)) {
      m[eq.slot] = eqId;
      return `* ${eq.name}を 手に入れた! ${m.name}が そうびした!`;
    }
    this.s.gold += Math.floor(eq.price / 2);
    return `* ${eq.name}を 手に入れたが つかえないので うっぱらった(+${Math.floor(eq.price / 2)}G)`;
  },

  addItem(id, n = 1) { this.s.items[id] = (this.s.items[id] || 0) + n; },
  takeItem(id, n = 1) {
    this.s.items[id] = Math.max(0, (this.s.items[id] || 0) - n);
    if (!this.s.items[id]) delete this.s.items[id];
  },

  /* ---------- セーブ ---------- */

  save() {
    try { localStorage.setItem(SAVE_KEY, JSON.stringify(this.s)); } catch (e) { /* file://でも動くよう握りつぶす */ }
  },
  load() {
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (!raw) return false;
      this.s = JSON.parse(raw);
      return true;
    } catch (e) { return false; }
  },
  hasSave() {
    try { return !!localStorage.getItem(SAVE_KEY); } catch (e) { return false; }
  },

  /* 全滅(QoL: お金没収なし・城で全回復) */
  gameOver() {
    this.healAll();
    this.s.map = "castle1"; this.s.x = 6; this.s.y = 4; this.s.dir = "down";
    this.s.ship.on = false;
    this.save();
  },
};

/* =========================================================
 * 戦闘
 * =======================================================*/

const Battle = {
  st: null,

  start(enemyIds) {
    const counts = {};
    this.st = {
      enemies: enemyIds.map((id) => {
        const def = MONSTERS[id];
        counts[id] = (counts[id] || 0) + 1;
        return { id, def, hp: def.hp, asleep: 0, tag: counts[id] };
      }),
      boss: enemyIds.some((id) => MONSTERS[id].boss),
      fleeTries: 0,
    };
    // 同種が複数いるときだけ A/B/C を付ける
    for (const e of this.st.enemies) {
      const same = this.st.enemies.filter((o) => o.id === e.id);
      e.label = same.length > 1 ? `${e.def.name}${"ABC"[e.tag - 1]}` : e.def.name;
    }
    return this.st;
  },

  aliveEnemies() { return this.st.enemies.filter((e) => e.hp > 0); },

  physDamage(atk, def) {
    const base = atk * 0.6 - def * 0.25;
    if (base <= 1) return rnd(0, 2);
    return Math.max(1, Math.round(base * frnd(0.8, 1.2)));
  },

  snap() {
    return {
      party: Game.s.party.map((m) => ({ hp: m.hp, mp: m.mp })),
      enemies: this.st.enemies.map((e) => e.hp),
    };
  },

  /* 1ラウンド解決。commands: {memberId: {type, ...}}。steps配列を返す */
  resolveRound(commands) {
    const steps = [];
    const push = (text, fx, extra) => steps.push(Object.assign({ text, fx, snap: this.snap() }, extra));

    // にげる(パーティ行動・先頭で判定)
    const runCmd = Object.values(commands).find((c) => c.type === "run");
    if (runCmd) {
      this.st.fleeTries++;
      if (this.st.boss) {
        push("* にげられない! まわりこまれてしまった!");
      } else if (Math.random() < 0.6 + this.st.fleeTries * 0.15) {
        push("* うまく にげきれた!", null, { end: "fled" });
        return steps;
      } else {
        push("* にげだした! …が まわりこまれてしまった!");
      }
    }

    // 行動順: 素早さ順(乱数つき)
    const actors = [];
    for (const m of Game.alive()) {
      const cmd = commands[m.id];
      if (!cmd || cmd.type === "run") continue;
      actors.push({ kind: "p", m, cmd, agi: Game.agiOf(m) * frnd(0.8, 1.2) });
    }
    for (const e of this.aliveEnemies()) {
      actors.push({ kind: "e", e, agi: e.def.agi * frnd(0.8, 1.2) });
    }
    actors.sort((a, b) => b.agi - a.agi);

    for (const m of Game.s.party) m.defending = false;
    for (const a of actors) {
      if (a.kind === "p") {
        if (a.m.hp <= 0) continue;
        if (a.m.asleep > 0) { a.m.asleep--; push(`* ${a.m.name}は ねむっている…`); continue; }
        this.playerAct(a.m, a.cmd, push);
      } else {
        if (a.e.hp <= 0) continue;
        if (Game.alive().length === 0) break;
        if (a.e.asleep > 0) { a.e.asleep--; push(`* ${a.e.label}は ねむっている…`); continue; }
        this.enemyAct(a.e, push);
        if (a.e.def.twice && a.e.hp > 0 && Game.alive().length) this.enemyAct(a.e, push); // ボスは2回行動
      }
      if (!this.aliveEnemies().length || !Game.alive().length) break;
    }

    // 終了判定
    if (!Game.alive().length) {
      push("* ぜんめつ してしまった…", "dead", { end: "lose" });
    } else if (!this.aliveEnemies().length) {
      const beaten = this.st.enemies.filter((e) => !e.fled); // 逃げた敵は経験値なし
      const exp = beaten.reduce((s, e) => s + e.def.exp, 0);
      const gold = beaten.reduce((s, e) => s + e.def.gold, 0);
      push("* まものたちを やっつけた!", null);
      push(`* ${exp}ポイントの けいけんちと ${gold}ゴールドを 手に入れた!`, null);
      Game.s.gold += gold;
      for (const t of Game.gainExp(exp)) push(t, "level");
      steps[steps.length - 1].end = "win";
      return steps;
    }
    return steps;
  },

  playerAct(m, cmd, push) {
    if (cmd.type === "attack") {
      let t = this.st.enemies[cmd.target];
      if (!t || t.hp <= 0) t = this.aliveEnemies()[0]; // QoL: 倒れていたら自動で別の敵へ
      if (!t) return;
      push(`* ${m.name}の こうげき!`);
      const crit = Math.random() < 1 / 16;
      let dmg = this.physDamage(Game.atkOf(m), t.def.def);
      if (crit) { dmg = Math.round(Game.atkOf(m) * frnd(0.9, 1.1)); push("* かいしんの いちげき!!", "flash"); }
      t.hp = Math.max(0, t.hp - dmg);
      push(`* ${t.label}に ${dmg}の ダメージ!`, "ehit", { hitEnemy: this.st.enemies.indexOf(t) });
      if (t.hp <= 0) push(`* ${t.label}を たおした!`, "edie", { hitEnemy: this.st.enemies.indexOf(t) });
    } else if (cmd.type === "spell") {
      const sp = SPELLS[cmd.spell];
      if (m.mp < sp.mp) { push(`* ${m.name}は じゅもんを となえたが MPが たりない!`); return; }
      m.mp -= sp.mp;
      push(`* ${m.name}は ${sp.name}を となえた!`, "flash");
      if (sp.type === "heal") {
        const t = Game.s.party[cmd.target] || m;
        const v = rnd(sp.power[0], sp.power[1]);
        t.hp = Math.min(Game.maxHp(t), t.hp + v);
        push(`* ${t.name}の きずが かいふくした!(+${v})`);
      } else if (sp.type === "dmg") {
        let t = this.st.enemies[cmd.target];
        if (!t || t.hp <= 0) t = this.aliveEnemies()[0];
        if (!t) return;
        const v = rnd(sp.power[0], sp.power[1]);
        t.hp = Math.max(0, t.hp - v);
        push(`* ${t.label}に ${v}の ダメージ!`, "ehit", { hitEnemy: this.st.enemies.indexOf(t) });
        if (t.hp <= 0) push(`* ${t.label}を たおした!`, "edie", { hitEnemy: this.st.enemies.indexOf(t) });
      } else if (sp.type === "dmgAll") {
        for (const t of this.aliveEnemies()) {
          const v = rnd(sp.power[0], sp.power[1]);
          t.hp = Math.max(0, t.hp - v);
          push(`* ${t.label}に ${v}の ダメージ!`, "ehit", { hitEnemy: this.st.enemies.indexOf(t) });
          if (t.hp <= 0) push(`* ${t.label}を たおした!`, "edie", { hitEnemy: this.st.enemies.indexOf(t) });
        }
      } else if (sp.type === "sleep") {
        let t = this.st.enemies[cmd.target];
        if (!t || t.hp <= 0) t = this.aliveEnemies()[0];
        if (!t) return;
        if (!t.def.boss && Math.random() < 0.65) {
          t.asleep = rnd(1, 2);
          push(`* ${t.label}は ねむってしまった!`);
        } else {
          push(`* しかし ${t.label}は ねむらない!`);
        }
      }
    } else if (cmd.type === "item") {
      if (!Game.s.items[cmd.item]) return;
      const it = ITEMS[cmd.item];
      Game.takeItem(cmd.item);
      const t = Game.s.party[cmd.target] || m;
      const v = rnd(it.power[0], it.power[1]);
      t.hp = Math.min(Game.maxHp(t), t.hp + v);
      push(`* ${m.name}は ${it.name}を つかった! ${t.name}のHPが ${v} かいふく!`);
    } else if (cmd.type === "defend") {
      m.defending = true;
      push(`* ${m.name}は みをまもっている`);
    }
  },

  enemyAct(e, push) {
    const acts = e.def.acts;
    let act = acts[rnd(0, acts.length - 1)];
    if (act === "heal" && e.hp > e.def.hp * 0.4) act = "attack";
    const targets = Game.alive();
    const t = targets[rnd(0, targets.length - 1)];

    if (act === "attack") {
      push(`* ${e.label}の こうげき!`);
      let dmg = this.physDamage(e.def.atk, Game.defOf(t));
      if (t.defending) dmg = Math.floor(dmg / 2);
      t.hp = Math.max(0, t.hp - dmg);
      push(`* ${t.name}は ${dmg}の ダメージを うけた!`, "phit");
      if (t.hp <= 0) push(`* ${t.name}は ちからつきた…`, "pdie");
    } else if (act === "spark" || act === "sparkPlus") {
      const v = act === "spark" ? rnd(8, 16) : rnd(20, 35);
      push(`* ${e.label}は じゅもんを となえた!`, "flash");
      const dmg = t.defending ? Math.floor(v / 2) : v;
      t.hp = Math.max(0, t.hp - dmg);
      push(`* ${t.name}は ${dmg}の ダメージを うけた!`, "phit");
      if (t.hp <= 0) push(`* ${t.name}は ちからつきた…`, "pdie");
    } else if (act === "breath") {
      push(`* ${e.label}は ほのおを はいた!`, "flash");
      for (const p of Game.alive()) {
        let dmg = rnd(10, 18);
        if (e.def.boss) dmg = rnd(18, 30);
        if (p.defending) dmg = Math.floor(dmg / 2);
        p.hp = Math.max(0, p.hp - dmg);
        push(`* ${p.name}は ${dmg}の ダメージを うけた!`, "phit");
        if (p.hp <= 0) push(`* ${p.name}は ちからつきた…`, "pdie");
      }
    } else if (act === "sleep") {
      push(`* ${e.label}は ねむりの じゅもんを となえた!`, "flash");
      if (Math.random() < 0.45) {
        t.asleep = rnd(1, 2);
        push(`* ${t.name}は ねむってしまった!`);
      } else {
        push(`* しかし ${t.name}は ねむらなかった!`);
      }
    } else if (act === "heal") {
      e.hp = Math.min(e.def.hp, e.hp + 60);
      push(`* ${e.label}は じぶんの きずを いやした!`, "flash");
    }

    // ぎんぷる系は逃げる
    if (e.def.flees && e.hp > 0 && Math.random() < 0.4) {
      e.hp = 0; e.fled = true;
      push(`* ${e.label}は にげだした!`, "edie", { hitEnemy: this.st.enemies.indexOf(e) });
    }
  },
};
