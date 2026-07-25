/* =========================================================
 * 人生モドキ 盤面描画(canvas・ドット絵)
 *
 * ファミコン風に、低解像度(280x210)で描いて CSS 側で拡大する。
 * スプライトはテキストグリッド(1文字=1ドット、. = 透過)。
 * 歩くキャラ・後ろを付いて歩く家族・立体マス・ゴールの城・
 * 木・雲・紙吹雪まで、見た目のすべてをここで持つ。
 * ロジックは持たない。
 * =======================================================*/

/* ---------- パレット ---------- */

const PX = {
  K: "#181008", W: "#f8f8f0", Y: "#f8d838", O: "#e07820", R: "#d83028",
  G: "#2c8c3c", g: "#1e6428", N: "#a05a20", n: "#6a3c14", B: "#3868d8",
  P: "#f088a8", F: "#f8c088", H: "#2c1c0c",
};

/* ---------- 人(8x12)。C=服 D=服の影 は呼び出し側で差し替える ---------- */

const MAN_STAND = [
  "..HHHH..",
  ".HHHHHH.",
  ".FFFFFF.",
  ".FKFFKF.",
  ".FFFFFF.",
  ".CCCCCC.",
  "FCCCCCCF",
  "FCCCCCCF",
  ".DDDDDD.",
  "..D..D..",
  "..D..D..",
  ".KK..KK.",
];
const MAN_WALK_A = MAN_STAND.slice(0, 9).concat([
  ".D....D.",
  ".D....D.",
  "KK....KK",
]);
const MAN_WALK_B = MAN_STAND.slice(0, 9).concat([
  "..D..D..",
  "...DD...",
  "..KKKK..",
]);

/* 子ども(6x9) */
const KID_STAND = [
  ".HHHH.",
  "HHHHHH",
  "FKFFKF",
  "FFFFFF",
  ".CCCC.",
  "CCCCCC",
  ".CCCC.",
  ".D..D.",
  ".K..K.",
];
const KID_WALK_A = KID_STAND.slice(0, 7).concat(["D....D", "K....K"]);
const KID_WALK_B = KID_STAND.slice(0, 7).concat(["..DD..", "..KK.."]);

/* ---------- マスのアイコン(8x8まで) ---------- */

const TILE_ICONS = {
  start: [
    "KRRRR...",
    "KRRRRRR.",
    "KRRRR...",
    "K.......",
    "K.......",
    "K.......",
    "KK......",
  ],
  goal: [
    ".KWWWWK.",
    ".KWWWWK.",
    "..KWWK..",
    "...KK...",
    "..KWWK..",
    ".KKKKKK.",
  ],
  fork: [
    ".NNNNN..",
    ".NNNNN..",
    "...KK...",
    "..NNNNN.",
    "..NNNNN.",
    "...KK...",
    "...KK...",
  ],
  payday: [
    "...KK...",
    "..KKKK..",
    ".KYYYYK.",
    "KYKYYKYK",
    "KYYKKYYK",
    "KYKKKKYK",
    "KYYKKYYK",
    ".KKKKKK.",
  ],
  money: [
    "..KKKK..",
    ".KYYYYK.",
    "KYWWYYYK",
    "KYWYYYYK",
    "KYYYYYYK",
    ".KYYYYK.",
    "..KKKK..",
  ],
  plain: [
    "...W....",
    "..WWW...",
    "WWWWWWW.",
    ".WWWWW..",
    "..W.W...",
    ".W...W..",
  ],
  stock: [
    "......GG",
    "......GG",
    "...YY.GG",
    "...YY.GG",
    "WW.YY.GG",
    "WW.YY.GG",
    "KKKKKKKK",
  ],
  gamble: [
    ".KKKKKK.",
    "KWWWWWWK",
    "KWKWWKWK",
    "KWWWWWWK",
    "KWWKKWWK",
    "KWKWWKWK",
    "KWWWWWWK",
    ".KKKKKK.",
  ],
  house: [
    "...KK...",
    "..KRRK..",
    ".KRRRRK.",
    "KRRRRRRK",
    ".KWWWWK.",
    ".KWNNWK.",
    ".KWNNWK.",
    ".KKKKKK.",
  ],
  marry: [
    ".KK..KK.",
    "KRRKKRRK",
    "KRWRRRRK",
    "KRRRRRRK",
    ".KRRRRK.",
    "..KRRK..",
    "...KK...",
  ],
  baby: [
    "...PP...",
    "...KK...",
    "..KWWK..",
    "..KWWK..",
    "..KWWK..",
    "..KWWK..",
    "..KKKK..",
  ],
  insurance: [
    ".KKKKKK.",
    "KBBWWBBK",
    "KBBWWBBK",
    "KBWWWWBK",
    "KBBWWBBK",
    ".KBWWBK.",
    "..KBBK..",
    "...KK...",
  ],
  accident: [
    "Y..YY..Y",
    ".YYYYYY.",
    ".YWWWWY.",
    "YYWWWWYY",
    ".YWWWWY.",
    ".YYYYYY.",
    "Y..YY..Y",
  ],
  job: [
    "..KKKK..",
    "..K..K..",
    "KKKKKKKK",
    "KNNNNNNK",
    "KNNKKNNK",
    "KNNNNNNK",
    "KKKKKKKK",
  ],
  jobchange: [
    "....BB..",
    ".BBBBBB.",
    "....BB..",
    "........",
    "..BB....",
    ".BBBBBB.",
    "..BB....",
  ],
  collect: [
    ".KKKKKK.",
    "KYYYYYYK",
    ".KKKKKK.",
    "KYYYYYYK",
    ".KKKKKK.",
    "KYYYYYYK",
    ".KKKKKK.",
  ],
  pay: [
    ".KKK..R.",
    "KYYYK.R.",
    "KYYYK.R.",
    ".KKK..R.",
    ".....RRR",
    "......R.",
  ],
  move: [
    "....W...",
    "....WW..",
    "WWWWWWW.",
    "WWWWWWWW",
    "WWWWWWW.",
    "....WW..",
    "....W...",
  ],
  choice: [
    "KKKKKKKK",
    "KWYYYYWK",
    "KYKKKKYK",
    "KYYYYKYK",
    "KYYKKYYK",
    "KYYYYYYK",
    "KWYKKYWK",
    "KKKKKKKK",
  ],
  happen: [
    "...WW...",
    "...WW...",
    "...WW...",
    "...WW...",
    "........",
    "...WW...",
    "...WW...",
  ],
  lottery: [
    "KKKKKKKK",
    "KWWWWWWK",
    "KWRRWWWK",
    "KWRRWWWK",
    "KWWWWWWK",
    "KKKKKKKK",
  ],
  fire: [
    "....R...",
    "...RR...",
    "..RRRR..",
    ".RRYYRR.",
    ".RYWWYR.",
    "RRYWWYRR",
    ".RRYYRR.",
    "..RRRR..",
  ],
};

/* ---------- 環境(木・雲・城・旗) ---------- */

/* 木は草地に埋もれないよう、明るい葉 + 濃い縁取り(T/t)で描く */
const TREE = [
  "...tttt...",
  "..tTTTTt..",
  ".tTTTTTTt.",
  "tTTtTTTTTt",
  "tTTTTTtTTt",
  ".tTTTTTTt.",
  "..tTTTTt..",
  "....NN....",
  "....NN....",
  "...nNNn...",
];
PX.T = "#3aa84e";
PX.t = "#124a1e";

const CLOUD = [
  "....WWWW.....",
  "..WWWWWWWW...",
  ".WWWWWWWWWWW.",
  "WWWWWWWWWWWWW",
];

const CASTLE = [
  "K.K.K.....K.K.K",
  "KKKKK.....KKKKK",
  "KWWWK.....KWWWK",
  "KWKWK.....KWKWK",
  "KWWWK.....KWWWK",
  "KWWWKKKKKKKWWWK",
  "KWWWWWWWWWWWWWK",
  "KWWKWWWKWWWKWWK",
  "KWWWWWNNNWWWWWK",
  "KWWWWWNNNWWWWWK",
  "KWWWWWNNNWWWWWK",
  "KKKKKKKKKKKKKKK",
];

const FLAG_A = ["RRRR", "RRRR", "RR.."];
const FLAG_B = ["RR..", "RRRR", "RRRR"];

/* 人生の節目を感じさせる建物たち(S=壁 b=窓あかり) */
PX.S = "#7f93a5";
PX.b = "#cfe8f8";

const SCHOOL = [
  ".KKKKKKKKKKKK.",
  ".KRRRRRRRRRRK.",
  ".KRRRRRRRRRRK.",
  ".KWWWWWWWWWWK.",
  ".KWBBWBBWBBWK.",
  ".KWWWWWWWWWWK.",
  ".KWBBWBBWBBWK.",
  ".KWWWWWWWWWWK.",
  ".KWWWWNNWWWWK.",
  ".KWWWWNNWWWWK.",
  ".KKKKKKKKKKKK.",
];

const CHURCH = [
  ".....KK.....",
  "....KKKK....",
  ".....KK.....",
  "....KWWK....",
  "...KWWWWK...",
  "..KWWWWWWK..",
  ".KWWWWWWWWK.",
  ".KWWWBBWWWK.",
  ".KWWWBBWWWK.",
  ".KWWWWWWWWK.",
  ".KWWWNNWWWK.",
  ".KWWWNNWWWK.",
  ".KKKKKKKKKK.",
];

const OFFICE = [
  "KKKKKKKKKK",
  "KSSSSSSSSK",
  "KSbSbSbSbK",
  "KSSSSSSSSK",
  "KSbSbSbSbK",
  "KSSSSSSSSK",
  "KSbSbSbSbK",
  "KSSSSSSSSK",
  "KSbSbSbSbK",
  "KSSSSSSSSK",
  "KSSSnnSSSK",
  "KKKKKKKKKK",
];

/* =========================================================
 * Board
 * =======================================================*/

const Board = {
  canvas: null,
  ctx: null,
  bg: null,          // 静的レイヤー(草地・道・マス)を焼き込んだ offscreen

  TILE: 19,          // マス上面の幅
  FACE: 13,          // マス上面の高さ
  DEPTH: 4,          // マス前面(立体に見せる部分)の高さ
  GAP_X: 22,
  GAP_Y: 28,
  OX: 9,
  OY: 14,
  W: 280,
  H: 210,

  tokenPos: {},      // プレイヤーid -> 足元座標
  anims: {},         // 移動アニメの進行状態
  trails: {},        // 家族が付いて歩くための足跡(過去のマス座標)
  followers: {},     // 家族スプライトの現在座標
  highlight: -1,
  particles: [],
  rafId: 0,

  KID_COLORS: ["#f0a030", "#58b0e8", "#a058d8", "#f0a030"],

  init() {
    this.canvas = document.getElementById("board");
    this.ctx = this.canvas.getContext("2d");
    this.ctx.imageSmoothingEnabled = false;

    this.tokenPos = {};
    this.anims = {};
    this.trails = {};
    this.followers = {};
    this.particles = [];
    for (const p of Game.players()) {
      this.tokenPos[p.id] = this.feetXY(p);
      this.trails[p.id] = [this.feetXY(p)];
      this.followers[p.id] = [];
    }

    this.buildStatic();
    cancelAnimationFrame(this.rafId);
    const loop = (t) => {
      this.draw(t);
      this.rafId = requestAnimationFrame(loop);
    };
    this.rafId = requestAnimationFrame(loop);
  },

  /* ---------- 座標 ---------- */

  cellTopLeft(cell) {
    return { x: this.OX + cell.col * this.GAP_X, y: this.OY + cell.row * this.GAP_Y };
  },

  cellCenter(cell) {
    const tl = this.cellTopLeft(cell);
    return { x: tl.x + 9, y: tl.y + 6 };
  },

  /* コマの足元。4人が重ならないよう上下2段にずらす */
  feetXY(p) {
    const tl = this.cellTopLeft(BOARD[p.pos]);
    const off = [[-5, 8], [5, 8], [-5, 12], [5, 12]][p.id % 4];
    return { x: tl.x + 9 + off[0], y: tl.y + off[1] };
  },

  /* ---------- スプライト描画 ---------- */

  sprite(ctx, rows, x, y, pal) {
    for (let j = 0; j < rows.length; j++) {
      const row = rows[j];
      for (let i = 0; i < row.length; i++) {
        const ch = row[i];
        if (ch === ".") continue;
        ctx.fillStyle = (pal && pal[ch]) || PX[ch] || "#f0f";
        ctx.fillRect(x + i, y + j, 1, 1);
      }
    }
  },

  shade(hex, k) {
    const n = parseInt(hex.slice(1), 16);
    const f = (v) => Math.max(0, Math.min(255, Math.round(v * k)));
    return `rgb(${f(n >> 16)},${f((n >> 8) & 255)},${f(n & 255)})`;
  },

  /* ---------- 静的レイヤー(1回だけ描く) ---------- */

  buildStatic() {
    const bg = document.createElement("canvas");
    bg.width = this.W;
    bg.height = this.H;
    const ctx = bg.getContext("2d");
    ctx.imageSmoothingEnabled = false;

    // 草地 + 濃淡(乱数は種固定。毎回同じ野原になる)
    ctx.fillStyle = "#2f8a3f";
    ctx.fillRect(0, 0, this.W, this.H);
    let seed = 7;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
    ctx.fillStyle = "#28793a";
    for (let i = 0; i < 420; i++) {
      ctx.fillRect((rnd() * this.W) | 0, (rnd() * this.H) | 0, 2, 1);
    }
    ctx.fillStyle = "#1e6a30";
    for (let i = 0; i < 90; i++) {
      const x = (rnd() * this.W) | 0, y = (rnd() * this.H) | 0;
      ctx.fillRect(x, y, 1, 2);
      ctx.fillRect(x + 2, y + 1, 1, 1);
    }
    for (let i = 0; i < 24; i++) {
      ctx.fillStyle = rnd() < 0.5 ? "#f8f8f0" : "#f8d838";
      ctx.fillRect((rnd() * this.W) | 0, (rnd() * this.H) | 0, 1, 1);
    }

    // 道(マスの下に敷く)
    for (const cell of BOARD) {
      const a = this.cellCenter(cell);
      for (const n of cell.next) {
        const b = this.cellCenter(BOARD[n.to]);
        ctx.strokeStyle = "#8a6d3a";
        ctx.lineWidth = 9;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        ctx.strokeStyle = "#e0cf9a";
        ctx.lineWidth = 7;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }

    // 長い道(分岐・合流)には進行方向の矢印
    for (const cell of BOARD) {
      const a = this.cellCenter(cell);
      for (const n of cell.next) {
        const b = this.cellCenter(BOARD[n.to]);
        if (Math.hypot(b.x - a.x, b.y - a.y) < 12) continue;
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        const ang = Math.atan2(b.y - a.y, b.x - a.x);
        ctx.save();
        ctx.translate(mx, my);
        ctx.rotate(ang);
        ctx.fillStyle = "#6a4d1a";
        ctx.beginPath(); ctx.moveTo(4, 0); ctx.lineTo(-3, -4); ctx.lineTo(-3, 4); ctx.fill();
        ctx.fillStyle = "#fff3c0";
        ctx.beginPath(); ctx.moveTo(3, 0); ctx.lineTo(-2, -3); ctx.lineTo(-2, 3); ctx.fill();
        ctx.restore();
      }
    }

    // マス(上面 + 前面で立体に)
    for (const cell of BOARD) {
      const tl = this.cellTopLeft(cell);
      const color = CELL_COLORS[cell.k] || "#8a8f98";
      // 前面(手前の影)
      ctx.fillStyle = this.shade(color, 0.5);
      ctx.fillRect(tl.x, tl.y + this.FACE, this.TILE, this.DEPTH);
      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.fillRect(tl.x, tl.y + this.FACE + this.DEPTH, this.TILE, 1);
      // 上面
      ctx.fillStyle = color;
      ctx.fillRect(tl.x, tl.y, this.TILE, this.FACE);
      ctx.fillStyle = this.shade(color, 1.35);
      ctx.fillRect(tl.x, tl.y, this.TILE, 1);
      ctx.fillRect(tl.x, tl.y, 1, this.FACE);
      ctx.fillStyle = this.shade(color, 0.7);
      ctx.fillRect(tl.x + this.TILE - 1, tl.y, 1, this.FACE);
      ctx.fillRect(tl.x, tl.y + this.FACE - 1, this.TILE, 1);
      // アイコン
      const icon = TILE_ICONS[cell.k];
      if (icon) {
        const iw = icon[0].length;
        this.sprite(ctx, icon, tl.x + ((this.TILE - iw) >> 1), tl.y + 2);
      }
    }

    // 建物(学生街 → 教会とオフィス街、という人生の順路)
    for (const [rows, x, y] of [[SCHOOL, 48, 62], [CHURCH, 24, 146], [OFFICE, 70, 146]]) {
      ctx.fillStyle = "rgba(0,0,0,0.25)";
      ctx.fillRect(x + 2, y + rows.length - 1, rows[0].length - 3, 2);
      this.sprite(ctx, rows, x, y);
    }

    // 木(道とぶつからない空き地に)
    for (const [x, y] of [[16, 70], [110, 68], [116, 150], [252, 176], [14, 124]]) {
      ctx.fillStyle = "rgba(0,0,0,0.25)";
      ctx.fillRect(x + 1, y + 9, 7, 2);
      this.sprite(ctx, TREE, x, y);
    }

    // ゴールの城(旗は動くので draw 側)
    this.castle = { x: 196, y: 176 };
    ctx.fillStyle = "rgba(0,0,0,0.25)";
    ctx.fillRect(this.castle.x + 1, this.castle.y + 11, 13, 2);
    this.sprite(ctx, CASTLE, this.castle.x, this.castle.y);

    this.bg = bg;
  },

  /* ---------- 毎フレーム ---------- */

  draw(t) {
    const ctx = this.ctx;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.bg, 0, 0);

    // 手番マスの点滅枠
    if (this.highlight >= 0 && Game.state && !Game.state.over) {
      const tl = this.cellTopLeft(BOARD[this.highlight]);
      const on = Math.floor(t / 260) % 2 === 0;
      ctx.strokeStyle = on ? "#fff36b" : "#f8f8f0";
      ctx.lineWidth = 1;
      ctx.strokeRect(tl.x - 1.5, tl.y - 1.5, this.TILE + 3, this.FACE + 3);
    }

    // 城の旗(2フレームではためく)
    const flag = Math.floor(t / 320) % 2 === 0 ? FLAG_A : FLAG_B;
    for (const fx of [this.castle.x + 2, this.castle.x + 12]) {
      ctx.fillStyle = PX.K;
      ctx.fillRect(fx, this.castle.y - 5, 1, 5);
      this.sprite(ctx, flag, fx + 1, this.castle.y - 5);
    }

    // 移動アニメを進める
    for (const [id, a] of Object.entries(this.anims)) {
      const k = a.dur <= 0 ? 1 : Math.min(1, (t - a.t0) / a.dur);
      this.tokenPos[id] = {
        x: a.fx + (a.tx - a.fx) * k,
        y: a.fy + (a.ty - a.fy) * k - Math.sin(k * Math.PI) * 3,
      };
      if (k >= 1) {
        this.tokenPos[id] = { x: a.tx, y: a.ty };
        delete this.anims[id];
        a.resolve();
      }
    }

    // 家族を足跡に沿って追わせる
    const drawables = [];
    if (Game.state) {
      for (const p of Game.players()) {
        const pos = this.tokenPos[p.id];
        if (!pos) continue;
        const moving = !!this.anims[p.id];
        drawables.push({ y: pos.y, kind: "man", p, pos, moving });

        const family = Math.min(4, (p.spouse ? 1 : 0) + p.kids);
        const fl = this.followers[p.id];
        const trail = this.trails[p.id];
        for (let i = 0; i < family; i++) {
          const back = trail.length - 2 - i;
          const target = back >= 0
            ? trail[back]
            : { x: pos.x + [-6, 6, -9, 9][i], y: pos.y + 3 };
          if (!fl[i]) fl[i] = { x: target.x, y: target.y };
          fl[i].x += (target.x - fl[i].x) * 0.16;
          fl[i].y += (target.y - fl[i].y) * 0.16;
          const walking = Math.hypot(target.x - fl[i].x, target.y - fl[i].y) > 1.2;
          drawables.push({
            y: fl[i].y, kind: i === 0 && p.spouse ? "spouse" : "kid",
            p, pos: fl[i], moving: walking, idx: i,
          });
        }
      }
    }

    // 奥のものから描く(足元のy座標でソート)
    drawables.sort((a, b) => a.y - b.y);
    for (const d of drawables) this.person(ctx, d, t);

    // 手番プレイヤーの頭上に矢印
    if (Game.state && !Game.state.over) {
      const cur = Game.cur();
      const pos = this.tokenPos[cur.id];
      if (pos) {
        const by = Math.round(pos.y - 16 + Math.sin(t / 180) * 1.5);
        const bx = Math.round(pos.x);
        ctx.fillStyle = "#fff36b";
        ctx.fillRect(bx - 2, by, 5, 2);
        ctx.fillRect(bx - 1, by + 2, 3, 1);
        ctx.fillRect(bx, by + 3, 1, 1);
      }
    }

    // 紙吹雪
    this.particles = this.particles.filter((pt) => {
      pt.x += pt.vx;
      pt.y += pt.vy;
      pt.vy += 0.06;
      pt.life--;
      if (pt.life <= 0 || pt.y > this.H) return false;
      ctx.fillStyle = pt.color;
      ctx.fillRect(Math.round(pt.x), Math.round(pt.y), Math.floor(pt.life / 20) % 2 ? 2 : 1, 1);
      return true;
    });

    // 雲(ゆっくり流れて、地面に影を落とす)
    for (const [speed, offset, y] of [[0.006, 0, 2], [0.004, 150, 9]]) {
      const x = ((t * speed + offset) % (this.W + 40)) - 20;
      ctx.globalAlpha = 0.22;
      ctx.fillStyle = "#0c3418";
      for (let j = 0; j < CLOUD.length; j++) {
        for (let i = 0; i < CLOUD[j].length; i++) {
          if (CLOUD[j][i] !== ".") ctx.fillRect(Math.round(x) + i + 3, y + j + 5, 1, 1);
        }
      }
      ctx.globalAlpha = 0.92;
      this.sprite(ctx, CLOUD, Math.round(x), y);
      ctx.globalAlpha = 1;
    }
  },

  /* 1人ぶん描く。d = {kind, p, pos, moving, idx} */
  person(ctx, d, t) {
    const x = Math.round(d.pos.x);
    const y = Math.round(d.pos.y);

    // 足元の影
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fillRect(x - 3, y, 6, 1);

    let rows, pal, w, h;
    if (d.kind === "kid") {
      const c = this.KID_COLORS[(d.idx || 0) % this.KID_COLORS.length];
      rows = d.moving ? (Math.floor(t / 90) % 2 ? KID_WALK_A : KID_WALK_B) : KID_STAND;
      pal = { C: c, D: this.shade(c, 0.6), H: "#3a2410" };
      w = 6; h = 9;
    } else {
      const c = d.kind === "spouse" ? "#e878a8" : d.p.color;
      const frames = [MAN_WALK_A, MAN_WALK_B];
      rows = d.moving ? frames[Math.floor(t / 90) % 2] : MAN_STAND;
      pal = { C: c, D: this.shade(c, 0.6) };
      if (d.kind === "spouse") pal.H = "#5a3010";
      w = 8; h = 12;
    }

    // 立ち止まっているときは、ときどき小さく弾む
    let bob = 0;
    if (!d.moving) {
      bob = Math.floor(t / 420 + d.p.id * 2 + (d.idx || 0) * 3) % 4 === 0 ? -1 : 0;
    } else if (rows === MAN_WALK_B || rows === KID_WALK_B) {
      bob = -1;
    }
    this.sprite(ctx, rows, x - (w >> 1), y - h + 1 + bob, pal);

    // ゴール済みは頭上に王冠
    if (d.kind === "man" && d.p.goaled) {
      ctx.fillStyle = PX.Y;
      ctx.fillRect(x - 2, y - h - 1 + bob, 5, 2);
      ctx.fillRect(x - 2, y - h - 2 + bob, 1, 1);
      ctx.fillRect(x, y - h - 2 + bob, 1, 1);
      ctx.fillRect(x + 2, y - h - 2 + bob, 1, 1);
    }
  },

  /* ---------- 移動(1マスぶん)。UI.step から呼ばれる ---------- */

  animateToken(p, dur) {
    const target = this.feetXY(p);
    const trail = this.trails[p.id];
    if (!trail.length || trail[trail.length - 1].x !== target.x || trail[trail.length - 1].y !== target.y) {
      trail.push(target);
      if (trail.length > 8) trail.shift();
    }
    const from = this.tokenPos[p.id] || target;
    if (dur <= 0) {
      this.tokenPos[p.id] = target;
      // 高速モードでは家族も瞬間移動(追いかけ待ちをなくす)
      const family = this.followers[p.id];
      for (let i = 0; i < family.length; i++) {
        const back = trail.length - 2 - i;
        if (back >= 0) family[i] = { ...trail[back] };
      }
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      this.anims[p.id] = {
        fx: from.x, fy: from.y, tx: target.x, ty: target.y,
        t0: performance.now(), dur, resolve,
      };
    });
  },

  /* ---------- ゴールの紙吹雪 ---------- */

  celebrate(p) {
    const cx = this.castle.x + 7;
    const cy = this.castle.y + 2;
    const colors = [p.color, "#f8d838", "#f8f8f0", "#f088a8", "#58b0e8"];
    for (let i = 0; i < 50; i++) {
      const ang = Math.random() * Math.PI - Math.PI;   // 上半分へ
      const v = 0.6 + Math.random() * 1.6;
      this.particles.push({
        x: cx, y: cy,
        vx: Math.cos(ang) * v,
        vy: Math.sin(ang) * v - 0.8,
        life: 50 + Math.random() * 40,
        color: colors[i % colors.length],
      });
    }
  },

  /* ---------- タイトル画面のデモ(4人が歩いているだけ) ---------- */

  titleDemo(canvas) {
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    const W = canvas.width, H = canvas.height;
    const loop = (t) => {
      ctx.fillStyle = "#2f8a3f";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#28793a";
      for (let x = 0; x < W; x += 7) ctx.fillRect(x + ((x / 7) % 2 ? 2 : 0), (x * 13) % H, 2, 1);
      ctx.fillStyle = "#e0cf9a";
      ctx.fillRect(0, H - 7, W, 5);
      ctx.fillStyle = "#8a6d3a";
      ctx.fillRect(0, H - 2, W, 1);
      PLAYER_SLOTS.forEach((slot, i) => {
        const frames = [MAN_WALK_A, MAN_WALK_B];
        const rows = frames[Math.floor(t / 130 + i) % 2];
        const bob = rows === MAN_WALK_B ? -1 : 0;
        const x = 18 + i * 36;
        ctx.fillStyle = "rgba(0,0,0,0.3)";
        ctx.fillRect(x - 3, H - 8, 6, 1);
        this.sprite(ctx, rows, x - 4, H - 19 + bob, { C: slot.color, D: this.shade(slot.color, 0.6) });
      });
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  },
};
