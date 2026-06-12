/* =========================================================
 * モドキクエストII UI
 * canvas描画・入力・ウィンドウ・進行制御
 * =======================================================*/

(function () {
  const $ = (s) => document.querySelector(s);
  const TILE = 32;
  const VIEW_W = 15, VIEW_H = 11;

  const canvas = $("#screen");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  let mode = "title"; // title / field / msg / battle / list / ending
  let msgQueue = [];
  let msgDone = null;       // メッセージ全部送った後のコールバック
  let actionQueue = [];     // イベントアクション
  let shake = 0, flashAlpha = 0;
  let battleCtx = null;     // {commands, current, steps, stepIdx, onEnd}
  let listCtx = null;       // 選択ウィンドウ {title, items[{label,value}], onPick, onCancel}

  /* ================= 描画 ================= */

  function draw() {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (mode === "title" || mode === "ending") return;
    if (mode === "battle") { drawBattle(); return; }
    drawField();
  }

  function drawField() {
    const s = Game.s;
    const map = MAPS[s.map];
    const rows = map.rows;
    const mw = rows[0].length, mh = rows.length;

    let camX = s.x - Math.floor(VIEW_W / 2);
    let camY = s.y - Math.floor(VIEW_H / 2);
    camX = Math.max(0, Math.min(mw - VIEW_W, camX));
    camY = Math.max(0, Math.min(mh - VIEW_H, camY));
    if (mw < VIEW_W) camX = Math.floor((mw - VIEW_W) / 2);
    if (mh < VIEW_H) camY = Math.floor((mh - VIEW_H) / 2);

    const ox = shake ? rnd2(-4, 4) : 0;

    for (let vy = 0; vy < VIEW_H; vy++) {
      for (let vx = 0; vx < VIEW_W; vx++) {
        const x = camX + vx, y = camY + vy;
        if (x < 0 || y < 0 || x >= mw || y >= mh) continue;
        ctx.drawImage(Sprites.tile(rows[y][x]), ox + vx * TILE, vy * TILE);
      }
    }

    // 宝箱
    for (const c of map.chests || []) {
      if (Game.s.opened[c.id]) continue;
      blit(chestSprite(), c.x - camX, c.y - camY, camX, camY, ox);
    }
    // NPC
    for (const n of map.npcs || []) {
      if (Game.npcGone(n)) continue;
      blit(Sprites.chara(n.art), n.x - camX, n.y - camY, camX, camY, ox);
    }
    // 船
    if (s.map === "world" && s.ship.has && !s.ship.on) {
      blit(shipSprite(), s.ship.x - camX, s.ship.y - camY, camX, camY, ox);
    }
    // 主人公(乗船中は船の絵)
    const px = s.x - camX, py = s.y - camY;
    if (s.ship.on) ctx.drawImage(shipSprite(), ox + px * TILE, py * TILE);
    else ctx.drawImage(Sprites.chara("hero"), ox + px * TILE, py * TILE);

    if (flashAlpha > 0) {
      ctx.fillStyle = `rgba(255,255,255,${flashAlpha})`;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  }

  function blit(img, vx, vy, camX, camY, ox) {
    if (vx < 0 || vy < 0 || vx >= VIEW_W || vy >= VIEW_H) return;
    ctx.drawImage(img, ox + vx * TILE, vy * TILE);
  }

  let chestCv = null;
  function chestSprite() {
    if (!chestCv) {
      chestCv = Sprites.build(
        ["................","................","................","....11111111....",
         "...1111111111...","...1222222221...","...1111111111...","...1113311111...",
         "...1113311111...","...1111111111...","...1111111111...","...2222222222...",
         "................","................","................","................"],
        ["#c2843b", "#8a5a20", "#e8c83b"], 2);
    }
    return chestCv;
  }
  let shipCv = null;
  function shipSprite() {
    if (!shipCv) {
      shipCv = Sprites.build(
        ["................",".......1........",".......11.......",".......111......",
         ".......1111.....",".......11111....",".......111111...",".......11.......",
         ".......11.......","..222222222222..","..322222222223..","...3222222223...",
         "....33333333....","................","................","................"],
        ["#e8e3d8", "#8a5a20", "#5a3a10"], 2);
    }
    return shipCv;
  }

  function drawBattle() {
    // 背景
    const zone = currentZone();
    ctx.fillStyle = zone === "cave" || zone === "final" ? "#15151c" : "#1c3344";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = zone === "cave" || zone === "final" ? "#2a2a3a" : "#2a5a2a";
    ctx.fillRect(0, canvas.height - 90, canvas.width, 90);

    const ox = shake ? rnd2(-6, 6) : 0;
    const enemies = Battle.st.enemies;
    const totalW = enemies.reduce((s, e) => s + Sprites.monster(e.def).width + 16, 0);
    let x = (canvas.width - totalW) / 2 + 8;
    for (let i = 0; i < enemies.length; i++) {
      const e = enemies[i];
      const img = Sprites.monster(e.def);
      if (e.hp > 0 || e.dying) {
        ctx.save();
        if (e.dying) ctx.globalAlpha = e.dying;
        if (battleCtx && battleCtx.hitFx === i) {
          ctx.globalCompositeOperation = "source-over";
          ctx.translate(rnd2(-5, 5), 0);
        }
        ctx.drawImage(img, ox + x, canvas.height - 100 - img.height);
        ctx.restore();
      }
      e.drawX = x; // ターゲット矢印用
      x += img.width + 16;
    }

    // ターゲット選択カーソル
    if (listCtx && listCtx.targetIdx != null) {
      const e = enemies[listCtx.items[listCtx.targetIdx].value];
      if (e) {
        ctx.fillStyle = "#ffd23b";
        const img = Sprites.monster(e.def);
        const tx = ox + e.drawX + img.width / 2;
        const ty = canvas.height - 110 - img.height;
        ctx.beginPath();
        ctx.moveTo(tx, ty + 10); ctx.lineTo(tx - 8, ty); ctx.lineTo(tx + 8, ty);
        ctx.fill();
      }
    }

    if (flashAlpha > 0) {
      ctx.fillStyle = `rgba(255,255,255,${flashAlpha})`;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  }

  function rnd2(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; }

  function currentZone() {
    const def = MAPS[Game.s.map];
    if (def.zone) return def.zone(Game.s.x, Game.s.y);
    return "field1";
  }

  /* ================= HUD ================= */

  function renderHud() {
    const s = Game.s;
    $("#hud-gold").textContent = `${s.gold} G`;
    $("#hud-place").textContent = MAPS[s.map].name;
    $("#hud-objective").textContent = "もくてき: " + currentObjective(s);

    const box = $("#party-status");
    box.innerHTML = "";
    for (const m of s.party) {
      const d = document.createElement("div");
      d.className = "member" + (m.hp <= 0 ? " dead" : m.hp < Game.maxHp(m) * 0.25 ? " danger" : "");
      d.innerHTML =
        `<div class="m-name">${m.name}</div>` +
        `<div>HP ${m.hp}/${Game.maxHp(m)}</div>` +
        `<div>MP ${m.mp}/${Game.maxMp(m)}</div>` +
        `<div>Lv ${m.lv}</div>`;
      box.appendChild(d);
    }
  }

  /* ================= メッセージ ================= */

  function showMsg(lines, done) {
    msgQueue = Array.isArray(lines) ? lines.slice() : [lines];
    msgDone = done || null;
    mode = mode === "battle" ? "battle" : "msg";
    nextMsg(true);
  }

  function nextMsg(first) {
    const w = $("#msg-window");
    if (!msgQueue.length) {
      w.classList.add("hidden");
      const cb = msgDone; msgDone = null;
      if (cb) cb();
      else if (mode === "msg") mode = "field";
      renderHud();
      return;
    }
    w.classList.remove("hidden");
    $("#msg-text").textContent = msgQueue.shift();
    renderHud();
  }

  /* ================= イベント実行 ================= */

  function runActions(actions, done) {
    actionQueue = actions.slice();
    pumpAction(done);
  }

  function pumpAction(done) {
    if (!actionQueue.length) {
      if (done) done();
      else { mode = "field"; draw(); renderHud(); Game.save(); }
      return;
    }
    const a = actionQueue.shift();
    const next = () => pumpAction(done);

    if (a.msg) { mode = "msg"; showMsg(a.msg, next); return; }
    if (a.flag) { Game.s.flags[a.flag] = true; next(); return; }
    if (a.gold) { Game.s.gold += a.gold; next(); return; }
    if (a.item) { Game.addItem(a.item); next(); return; }
    if (a.takeItem) { Game.takeItem(a.takeItem); next(); return; }
    if (a.heal) { Game.healAll(); next(); return; }
    if (a.join) { Game.join(a.join); next(); return; }
    if (a.learnEquip) { mode = "msg"; showMsg(Game.gainEquip(a.learnEquip), next); return; }
    if (a.warp) { Game.transfer(a.warp); draw(); next(); return; }
    if (a.shop) { openShop(a.shop, next); return; }
    if (a.inn) { openInn(a.inn, next); return; }
    if (a.battle) {
      startBattle(a.battle, (result) => {
        if (result === "win") { actionQueue = (a.win || []).concat(actionQueue); }
        else { actionQueue = []; }
        pumpAction(done);
      });
      return;
    }
    if (a.ending) { showEnding(); return; }
    next();
  }

  /* ================= リスト選択ウィンドウ ================= */

  function openList(title, items, onPick, onCancel, targetSelect) {
    listCtx = { title, items, idx: 0, onPick, onCancel, targetIdx: targetSelect ? 0 : null };
    renderList();
    mode = mode === "battle" ? "battle" : "list";
    $("#list-window").classList.remove("hidden");
  }

  function renderList() {
    $("#list-title").textContent = listCtx.title;
    const box = $("#list-items");
    box.innerHTML = "";
    listCtx.items.forEach((it, i) => {
      const d = document.createElement("div");
      d.className = "list-item" + (i === listCtx.idx ? " sel" : "");
      d.textContent = (i === listCtx.idx ? "▶ " : "  ") + it.label;
      d.addEventListener("click", () => { listCtx.idx = i; pickList(); });
      box.appendChild(d);
    });
    if (listCtx.targetIdx != null) { listCtx.targetIdx = listCtx.idx; draw(); }
  }

  function moveList(d) {
    listCtx.idx = (listCtx.idx + d + listCtx.items.length) % listCtx.items.length;
    renderList();
  }

  function pickList() {
    const it = listCtx.items[listCtx.idx];
    const cb = listCtx.onPick;
    closeList();
    cb(it.value, it);
  }

  function cancelList() {
    const cb = listCtx.onCancel;
    closeList();
    if (cb) cb();
  }

  function closeList() {
    listCtx = null;
    $("#list-window").classList.add("hidden");
  }

  /* ================= ショップ・宿屋 ================= */

  function openShop(shopId, done) {
    const shop = SHOPS[shopId];
    const items = [];
    for (const eq of shop.items) {
      const e = EQUIP[eq];
      items.push({ label: `${e.name} ${e.price}G (${e.atk ? "こうげき+" + e.atk : "しゅび+" + e.def})`, value: { eq } });
    }
    for (const g of shop.goods) {
      items.push({ label: `${ITEMS[g].name} ${ITEMS[g].price}G`, value: { item: g } });
    }
    items.push({ label: "やめる", value: null });
    openList(`${shop.name}(しょじ金 ${Game.s.gold}G)`, items, (v) => {
      if (!v) { done(); return; }
      if (v.eq) {
        const r = Game.buyEquip(v.eq);
        showMsg(r.msg, () => openShop(shopId, done));
      } else {
        const it = ITEMS[v.item];
        if (Game.s.gold < it.price) { showMsg("* お金が たりない!", () => openShop(shopId, done)); return; }
        Game.s.gold -= it.price;
        Game.addItem(v.item);
        showMsg(`* ${it.name}を かった!`, () => openShop(shopId, done));
      }
    }, done);
  }

  function openInn(price, done) {
    openList(`やどや(ひとばん ${price}G)`, [
      { label: `とまる(${price}G)`, value: true },
      { label: "やめる", value: false },
    ], (v) => {
      if (!v) { done(); return; }
      if (Game.s.gold < price) { showMsg("* お金が たりない!", done); return; }
      Game.s.gold -= price;
      Game.healAll();
      Game.save();
      showMsg(["* ゆっくり やすんだ! HPとMPが ぜんかいふくした!", "* (オートセーブ しました)"], done);
    }, done);
  }

  /* ================= フィールドメニュー ================= */

  function openFieldMenu() {
    openList("メニュー", [
      { label: "つよさ", value: "status" },
      { label: "じゅもん", value: "spell" },
      { label: "どうぐ", value: "item" },
      { label: "セーブ", value: "save" },
    ], (v) => {
      if (v === "status") {
        const lines = Game.s.party.map((m) => {
          const w = m.weapon ? EQUIP[m.weapon].name : "なし";
          const ar = m.armor ? EQUIP[m.armor].name : "なし";
          const sh = m.shield ? EQUIP[m.shield].name : "なし";
          return `${m.name} Lv${m.lv} HP${m.hp}/${Game.maxHp(m)} MP${m.mp}/${Game.maxMp(m)} こうげき${Game.atkOf(m)} しゅび${Game.defOf(m)} [${w}/${ar}/${sh}]`;
        });
        lines.push(`しょじ金 ${Game.s.gold}G / げんきそう ${Game.s.items.herb || 0}こ`);
        showMsg(lines);
      } else if (v === "spell") {
        fieldSpellMenu();
      } else if (v === "item") {
        fieldItemMenu();
      } else if (v === "save") {
        Game.save();
        showMsg("* セーブしました!(マップいどう・やどや・レベルアップでも かってに セーブされます)");
      }
    });
  }

  function fieldSpellMenu() {
    const casters = Game.alive().filter((m) => Game.spellsOf(m).some((sp) => SPELLS[sp].field));
    if (!casters.length) { showMsg("* フィールドで つかえる じゅもんを だれも しらない"); return; }
    const items = [];
    for (const m of casters) {
      for (const sp of Game.spellsOf(m)) {
        if (!SPELLS[sp].field) continue;
        items.push({ label: `${m.name}の ${SPELLS[sp].name}(MP${SPELLS[sp].mp})`, value: { m, sp } });
      }
    }
    items.push({ label: "やめる", value: null });
    openList("じゅもん", items, (v) => {
      if (!v) return;
      const sp = SPELLS[v.sp];
      if (v.m.mp < sp.mp) { showMsg("* MPが たりない!"); return; }
      if (sp.type === "heal") {
        pickAlly((t) => {
          v.m.mp -= sp.mp;
          const heal = rnd2(sp.power[0], sp.power[1]);
          t.hp = Math.min(Game.maxHp(t), t.hp + heal);
          showMsg(`* ${t.name}のHPが ${heal} かいふくした!`);
        });
      } else if (v.sp === "modori") {
        v.m.mp -= sp.mp;
        Game.transfer({ map: "world", x: 8, y: 7 });
        Game.s.ship.on = false;
        showMsg("* ガンバリアじょうの まえに もどった!");
        draw();
      }
    });
  }

  function fieldItemMenu() {
    const items = [];
    if (Game.s.items.herb) items.push({ label: `げんきそう(のこり${Game.s.items.herb})`, value: "herb" });
    if (Game.s.items.wing) items.push({ label: `ハトのつばさ(のこり${Game.s.items.wing})`, value: "wing" });
    if (Game.s.items.bakeneko) items.push({ label: "ばけねこ草(だいじなもの)", value: null });
    if (!items.length) { showMsg("* どうぐを なにも もっていない"); return; }
    items.push({ label: "やめる", value: null });
    openList("どうぐ", items, (v) => {
      if (!v) return;
      if (v === "herb") {
        pickAlly((t) => {
          Game.takeItem("herb");
          const heal = rnd2(ITEMS.herb.power[0], ITEMS.herb.power[1]);
          t.hp = Math.min(Game.maxHp(t), t.hp + heal);
          showMsg(`* ${t.name}のHPが ${heal} かいふくした!`);
        });
      } else if (v === "wing") {
        Game.takeItem("wing");
        Game.transfer({ map: "world", x: 8, y: 7 });
        Game.s.ship.on = false;
        showMsg("* ハトが むれを なして はこんでくれた! ガンバリアじょうの まえだ!");
        draw();
      }
    });
  }

  function pickAlly(cb) {
    openList("だれに?", Game.s.party.map((m, i) => ({ label: `${m.name}(HP ${m.hp}/${Game.maxHp(m)})`, value: m })), cb);
  }

  /* ================= 戦闘 ================= */

  function startBattle(enemyIds, onEnd) {
    Battle.start(enemyIds);
    battleCtx = { onEnd: onEnd || null, commands: {}, idx: 0, hitFx: null };
    mode = "battle";
    draw();
    const names = [...new Set(Battle.st.enemies.map((e) => e.def.name))];
    showMsg(names.map((n) => `* ${n}が あらわれた!`), askCommand);
  }

  function askCommand() {
    mode = "battle";
    const alive = Game.alive();
    if (battleCtx.idx >= alive.length) { execRound(); return; }
    const m = alive[battleCtx.idx];
    if (m.asleep > 0) { battleCtx.commands[m.id] = { type: "defend" }; battleCtx.idx++; askCommand(); return; }

    const items = [{ label: "たたかう", value: "attack" }];
    if (Game.spellsOf(m).length) items.push({ label: "じゅもん", value: "spell" });
    if (Game.s.items.herb) items.push({ label: "どうぐ", value: "item" });
    items.push({ label: "ぼうぎょ", value: "defend" });
    if (battleCtx.idx === 0) items.push({ label: "にげる", value: "run" });

    openList(`${m.name}は どうする?`, items, (v) => {
      if (v === "attack") {
        pickEnemy((ti) => { battleCtx.commands[m.id] = { type: "attack", target: ti }; battleCtx.idx++; askCommand(); }, askCommand);
      } else if (v === "spell") {
        const sps = Game.spellsOf(m).filter((sp) => !SPELLS[sp].fieldOnly).map((sp) => ({
          label: `${SPELLS[sp].name}(MP${SPELLS[sp].mp})`, value: sp,
        }));
        sps.push({ label: "やめる", value: null });
        openList("じゅもん", sps, (sp) => {
          if (!sp) { askCommand(); return; }
          const def = SPELLS[sp];
          if (m.mp < def.mp) { showMsg("* MPが たりない!", askCommand); return; }
          if (def.type === "heal") {
            openList("だれに?", Game.s.party.map((p, i) => ({ label: `${p.name}(HP ${p.hp}/${Game.maxHp(p)})`, value: i })), (ti) => {
              battleCtx.commands[m.id] = { type: "spell", spell: sp, target: ti };
              battleCtx.idx++; askCommand();
            }, askCommand);
          } else if (def.type === "dmg" || def.type === "sleep") {
            pickEnemy((ti) => {
              battleCtx.commands[m.id] = { type: "spell", spell: sp, target: ti };
              battleCtx.idx++; askCommand();
            }, askCommand);
          } else {
            battleCtx.commands[m.id] = { type: "spell", spell: sp };
            battleCtx.idx++; askCommand();
          }
        }, askCommand);
      } else if (v === "item") {
        openList("だれに?", Game.s.party.map((p, i) => ({ label: `${p.name}(HP ${p.hp}/${Game.maxHp(p)})`, value: i })), (ti) => {
          battleCtx.commands[m.id] = { type: "item", item: "herb", target: ti };
          battleCtx.idx++; askCommand();
        }, askCommand);
      } else if (v === "defend") {
        battleCtx.commands[m.id] = { type: "defend" };
        battleCtx.idx++; askCommand();
      } else if (v === "run") {
        battleCtx.commands[m.id] = { type: "run" };
        execRound();
      }
    });
  }

  function pickEnemy(cb, cancel) {
    const alive = Battle.aliveEnemies();
    if (alive.length === 1) { cb(Battle.st.enemies.indexOf(alive[0])); return; }
    openList("どれに?", alive.map((e) => ({ label: e.label, value: Battle.st.enemies.indexOf(e) })), cb, cancel, true);
  }

  function execRound() {
    const steps = Battle.resolveRound(battleCtx.commands);
    battleCtx.commands = {};
    battleCtx.idx = 0;
    playSteps(steps, 0);
  }

  function playSteps(steps, i) {
    if (i >= steps.length) { askCommand(); return; }
    const st = steps[i];
    $("#msg-window").classList.remove("hidden");
    $("#msg-text").textContent = st.text;

    // エフェクト
    if (st.fx === "phit" || st.fx === "pdie") { shake = 1; setTimeout(() => { shake = 0; draw(); }, 220); }
    if (st.fx === "flash") { flashAlpha = 0.7; setTimeout(() => { flashAlpha = 0; draw(); }, 130); }
    if (st.fx === "ehit") { battleCtx.hitFx = st.hitEnemy; setTimeout(() => { battleCtx.hitFx = null; draw(); }, 180); }
    if (st.fx === "edie" && st.hitEnemy != null) {
      const e = Battle.st.enemies[st.hitEnemy];
      e.dying = 0.6;
      setTimeout(() => { e.dying = 0; draw(); }, 250);
    }
    renderHudSnap(st.snap);
    draw();

    if (st.end) {
      setTimeout(() => finishBattle(st.end), 700);
      return;
    }
    const wait = st.fx ? 520 : 420;
    battleCtx.timer = setTimeout(() => playSteps(steps, i + 1), wait);
    battleCtx.skip = () => { clearTimeout(battleCtx.timer); battleCtx.skip = null; playSteps(steps, i + 1); };
  }

  function renderHudSnap(snap) {
    const box = $("#party-status");
    box.innerHTML = "";
    Game.s.party.forEach((m, i) => {
      const hp = snap ? snap.party[i].hp : m.hp;
      const mp = snap ? snap.party[i].mp : m.mp;
      const d = document.createElement("div");
      d.className = "member" + (hp <= 0 ? " dead" : hp < Game.maxHp(m) * 0.25 ? " danger" : "");
      d.innerHTML =
        `<div class="m-name">${m.name}</div><div>HP ${hp}/${Game.maxHp(m)}</div>` +
        `<div>MP ${mp}/${Game.maxMp(m)}</div><div>Lv ${m.lv}</div>`;
      box.appendChild(d);
    });
  }

  function finishBattle(result) {
    $("#msg-window").classList.add("hidden");
    const onEnd = battleCtx.onEnd;
    battleCtx = null;

    if (result === "lose") {
      Game.gameOver();
      mode = "field";
      draw(); renderHud();
      showMsg([
        "* めのまえが まっくらに なった…",
        "王さま「おお ガンバ!しんでしまうとは なにごとだ!」",
        "王さま「…まあ よい。お金は とらずに おいてやろう。かいふくも しておいたぞ(QoLじゃ)」",
      ]);
      return;
    }
    mode = "field";
    Game.save();
    draw(); renderHud();
    if (onEnd) onEnd(result === "fled" ? "fled" : "win");
  }

  /* ================= フィールド操作 ================= */

  function tryMove(dx, dy) {
    const r = Game.move(dx, dy);
    draw(); renderHud();
    if (!r.trigger) return;
    const t = r.trigger;
    if (t.type === "portal") {
      Game.transfer(t.to);
      draw(); renderHud();
    } else if (t.type === "npc") {
      const n = t.npc;
      if (n.event) {
        const actions = EVENTS[n.event](Game.s);
        if (actions.length) runActions(actions);
      } else if (n.text) {
        showMsg(n.text);
      }
    } else if (t.type === "chest") {
      const c = t.chest;
      if (c.event) {
        Game.s.opened[c.id] = true;
        runActions(EVENTS[c.event](Game.s));
      } else {
        Game.s.opened[c.id] = true;
        const msgs = [];
        if (c.gold) { Game.s.gold += c.gold; msgs.push(`* たからばこを あけた! ${c.gold}ゴールドを 手に入れた!`); }
        if (c.item) { Game.addItem(c.item); msgs.push(`* たからばこを あけた! ${ITEMS[c.item].name}を 手に入れた!`); }
        Game.save();
        showMsg(msgs);
      }
    } else if (t.type === "encounter") {
      startBattle(t.enemies, null);
    }
  }

  /* ================= タイトル・エンディング ================= */

  function showTitle() {
    mode = "title";
    $("#title-screen").classList.remove("hidden");
    $("#game-ui").classList.add("hidden");
    $("#ending-screen").classList.add("hidden");
    $("#continue-btn").style.display = Game.hasSave() ? "" : "none";
  }

  function startGame(useLoad) {
    if (useLoad && Game.load()) { /* つづきから */ }
    else Game.newGame();
    $("#title-screen").classList.add("hidden");
    $("#game-ui").classList.remove("hidden");
    mode = "field";
    draw(); renderHud();
    if (!Game.s.flags.quest) {
      showMsg(["* ガンバリアじょうの 王さまが よんでいる。たまの ある方向(うえ)へ すすんで 話しかけよう", "* そうさ: 矢印キーで いどう / ぶつかると はなす / Xか Escで メニュー"]);
    }
  }

  function showEnding() {
    mode = "ending";
    $("#game-ui").classList.add("hidden");
    $("#ending-screen").classList.remove("hidden");
    const s = Game.s;
    $("#ending-stats").textContent =
      `とうたつレベル: ${s.party.map((m) => `${m.name} Lv${m.lv}`).join(" / ")} ` +
      `/ あるいた歩数: ${s.steps}歩`;
    try { localStorage.removeItem(SAVE_KEY); } catch (e) {}
  }

  /* ================= 入力 ================= */

  function onKey(e) {
    const k = e.key;
    if (mode === "title" || mode === "ending") return;

    if (listCtx) {
      if (k === "ArrowUp" || k === "w") { moveList(-1); e.preventDefault(); }
      else if (k === "ArrowDown" || k === "s") { moveList(1); e.preventDefault(); }
      else if (k === "Enter" || k === " " || k === "z") { pickList(); e.preventDefault(); }
      else if (k === "Escape" || k === "x" || k === "Backspace") { cancelList(); e.preventDefault(); }
      return;
    }

    if (!$("#msg-window").classList.contains("hidden")) {
      if (k === "Enter" || k === " " || k === "z" || k === "Escape" || k === "x") {
        if (battleCtx && battleCtx.skip) battleCtx.skip();
        else nextMsg();
        e.preventDefault();
      }
      return;
    }

    if (mode === "field") {
      if (k === "ArrowUp" || k === "w") { tryMove(0, -1); e.preventDefault(); }
      else if (k === "ArrowDown" || k === "s") { tryMove(0, 1); e.preventDefault(); }
      else if (k === "ArrowLeft" || k === "a") { tryMove(-1, 0); e.preventDefault(); }
      else if (k === "ArrowRight" || k === "d") { tryMove(1, 0); e.preventDefault(); }
      else if (k === "Escape" || k === "x" || k === "Enter") { openFieldMenu(); e.preventDefault(); }
    }
  }

  document.addEventListener("keydown", onKey);

  // タッチ・クリック操作
  document.querySelectorAll("[data-pad]").forEach((b) => {
    b.addEventListener("click", () => {
      const d = b.dataset.pad;
      const fake = { key: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight", a: "Enter", b: "Escape" }[d], preventDefault: () => {} };
      onKey(fake);
    });
  });
  $("#msg-window").addEventListener("click", () => {
    if (battleCtx && battleCtx.skip) battleCtx.skip();
    else nextMsg();
  });

  $("#start-btn").addEventListener("click", () => startGame(false));
  $("#continue-btn").addEventListener("click", () => startGame(true));
  $("#ending-restart").addEventListener("click", showTitle);

  showTitle();
})();
