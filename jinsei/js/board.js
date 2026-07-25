/* =========================================================
 * 人生モドキ ボード描画(canvas)
 * 道・マス・コマ(車)を描く。ロジックは持たない。
 * =======================================================*/

const Board = {
  canvas: null,
  ctx: null,

  TILE: 38,
  GAP_X: 44,
  GAP_Y: 56,
  OX: 22,
  OY: 20,

  tokenPos: {},   // プレイヤーid -> 描画中の座標(アニメ用)
  highlight: -1,  // 手番プレイヤーのマスを光らせる

  init() {
    this.canvas = document.getElementById("board");
    this.ctx = this.canvas.getContext("2d");
    this.tokenPos = {};
    for (const p of Game.players()) this.tokenPos[p.id] = this.tokenXY(p);
    this.draw();
  },

  cellXY(cell) {
    return {
      x: this.OX + cell.col * this.GAP_X + this.TILE / 2,
      y: this.OY + cell.row * this.GAP_Y + this.TILE / 2,
    };
  },

  /* コマはマスの下半分に4台ぶん並べる(マスのアイコンを隠さないため) */
  tokenXY(p) {
    const c = this.cellXY(BOARD[p.pos]);
    const off = [[-9, 5], [9, 5], [-9, 14], [9, 14]][p.id % 4];
    return { x: c.x + off[0], y: c.y + off[1] };
  },

  /* ---------- 描画本体 ---------- */

  draw() {
    const ctx = this.ctx;
    const W = this.canvas.width;
    const H = this.canvas.height;

    // 盤面(フェルト風)
    ctx.fillStyle = "#1d5c3a";
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 20) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += 20) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // 道
    ctx.lineCap = "round";
    for (const cell of BOARD) {
      const a = this.cellXY(cell);
      for (const n of cell.next) {
        const b = this.cellXY(BOARD[n.to]);
        ctx.strokeStyle = "#f5eecb";
        ctx.lineWidth = 10;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        this.arrow(a, b);
      }
    }

    // マス
    for (const cell of BOARD) {
      const c = this.cellXY(cell);
      const size = cell.k === "goal" || cell.k === "start" ? this.TILE + 4 : this.TILE;
      this.tile(c.x, c.y, size, CELL_COLORS[cell.k] || "#8a8f98", cell.idx === this.highlight);
      ctx.font = "16px serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(cell.e || "・", c.x, c.y - 5);   // コマの居場所を下に空けておく
    }

    // コマ(車)
    for (const p of Game.players()) {
      const pos = this.tokenPos[p.id];
      if (pos) this.car(pos.x, pos.y, p);
    }
  },

  /* 道の途中に進行方向の矢印。どっち回りか ひと目で分かるように。 */
  arrow(a, b) {
    const ctx = this.ctx;
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const ang = Math.atan2(b.y - a.y, b.x - a.x);
    ctx.save();
    ctx.translate(mx, my);
    ctx.rotate(ang);
    ctx.fillStyle = "rgba(120, 96, 40, 0.55)";
    ctx.beginPath();
    ctx.moveTo(3, 0);
    ctx.lineTo(-2.5, -3.2);
    ctx.lineTo(-2.5, 3.2);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  },

  tile(cx, cy, size, color, glow) {
    const ctx = this.ctx;
    const x = cx - size / 2;
    const y = cy - size / 2;
    const r = 6;

    if (glow) {
      ctx.save();
      ctx.shadowColor = "#fff36b";
      ctx.shadowBlur = 14;
      ctx.fillStyle = "#fff36b";
      this.roundRect(x - 3, y - 3, size + 6, size + 6, r + 2);
      ctx.fill();
      ctx.restore();
    }

    ctx.fillStyle = "rgba(0,0,0,0.35)";
    this.roundRect(x + 2, y + 3, size, size, r);
    ctx.fill();

    ctx.fillStyle = color;
    this.roundRect(x, y, size, size, r);
    ctx.fill();

    ctx.strokeStyle = "rgba(255,255,255,0.55)";
    ctx.lineWidth = 2;
    this.roundRect(x, y, size, size, r);
    ctx.stroke();
  },

  roundRect(x, y, w, h, r) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  },

  /* 車。乗っている家族の数を屋根の上の点で表す(人生ゲームのピン) */
  car(x, y, p) {
    const ctx = this.ctx;
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.beginPath();
    ctx.ellipse(x, y + 6, 8, 2.5, 0, 0, Math.PI * 2);
    ctx.fill();

    // 家族ピン(車に乗っている人の数)
    const pins = Math.min(4, (p.spouse ? 1 : 0) + p.kids);
    for (let i = 0; i < pins; i++) {
      ctx.fillStyle = "#ffe9a8";
      ctx.beginPath();
      ctx.arc(x - 5 + i * 3.5, y - 7, 1.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // 車体
    ctx.fillStyle = p.color;
    this.roundRect(x - 8, y - 5, 16, 9, 3);
    ctx.fill();
    ctx.strokeStyle = p.goaled ? "#fff36b" : "rgba(0,0,0,0.65)";
    ctx.lineWidth = p.goaled ? 2 : 1;
    this.roundRect(x - 8, y - 5, 16, 9, 3);
    ctx.stroke();

    // 窓
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    this.roundRect(x - 5, y - 3, 10, 3.5, 1);
    ctx.fill();

    // タイヤ
    ctx.fillStyle = "#20202a";
    ctx.beginPath(); ctx.arc(x - 4.5, y + 4, 2, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x + 4.5, y + 4, 2, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  },

  /* ---------- 1マス分の移動アニメ ---------- */

  animateToken(p, dur) {
    const target = this.tokenXY(p);
    const from = this.tokenPos[p.id] || target;
    if (dur <= 0) {
      this.tokenPos[p.id] = target;
      this.draw();
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      const t0 = performance.now();
      const tick = () => {
        const k = Math.min(1, (performance.now() - t0) / dur);
        this.tokenPos[p.id] = {
          x: from.x + (target.x - from.x) * k,
          y: from.y + (target.y - from.y) * k - Math.sin(k * Math.PI) * 12,
        };
        this.draw();
        if (k < 1) requestAnimationFrame(tick);
        else {
          this.tokenPos[p.id] = target;
          this.draw();
          resolve();
        }
      };
      requestAnimationFrame(tick);
    });
  },
};
