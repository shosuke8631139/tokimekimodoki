/* =========================================================
 * 人生モドキ イベントカットイン演出(scenes.js)
 *
 * 結婚・出産・事故・ゴールなど、人生の大イベントで
 * 画面中央にファミコン風の「イベントシーン」を出す。
 * 内部解像度 192x112 の canvas にドット絵を描き、CSS で拡大。
 * スプライトは board.js と同じテキストグリッド方式
 * (1文字=1ドット、`.`=透過)。ここは見た目だけを持ち、
 * ロジックは持たない。他の JS / CSS には依存しない。
 *
 * 使い方:
 *   await Scenes.play("marry", { color: p.color });
 *   opts = { color: 服の色, count: 人数, fast: 短縮, label: 見出し上書き }
 * =======================================================*/

const Scenes = (() => {

  /* ---------- 定数 ---------- */

  const W = 192;          // canvas 内部解像度
  const H = 112;
  const DUR_NORMAL = 1600;   // 通常のアニメ時間
  const DUR_FAST = 400;      // fast 時
  const HOLD_NORMAL = 400;   // 終了後の静止時間
  const HOLD_FAST = 150;

  /* ---------- パレット(ファミコン風・自己完結) ---------- */

  const C = {
    K: "#181008",  // 黒(輪郭)
    W: "#f8f8f0",  // 白
    Y: "#f8d838",  // 黄
    y: "#fff8b0",  // 淡黄(窓明かり)
    O: "#e07820",  // 橙
    R: "#d83028",  // 赤
    G: "#2c8c3c",  // 緑
    N: "#a05a20",  // 茶(木・扉)
    n: "#6a3c14",  // 濃茶
    B: "#3868d8",  // 青
    b: "#a8d8f8",  // 淡青(ガラス)
    P: "#f088a8",  // 桃
    F: "#f8c088",  // 肌
    H: "#2c1c0c",  // 髪
    S: "#9098a8",  // 灰(岩・ビル)
    s: "#565c68",  // 濃灰
    E: "#e0d8c8",  // ドレスの影
  };

  /* 乱数テーブル(種固定。毎回同じ散らばりになる) */
  const RND = (() => {
    const a = [];
    let s = 20260725;
    for (let i = 0; i < 96; i++) {
      s = (s * 1103515245 + 12345) >>> 0;
      a.push(s / 4294967296);
    }
    return a;
  })();

  /* =========================================================
   * スプライト定義(1文字=1ドット、. = 透過)
   * =======================================================*/

  /* ---------- 主人公(16x22)。C=服 D=服の影 は差し替え ---------- */

  const HERO_STAND = [
    "....HHHHHHHH....",
    "...HHHHHHHHHH...",
    "..HHHHHHHHHHHH..",
    "..HHFFFFFFFFHH..",
    "..HFFFFFFFFFFH..",
    "...FFKKFFKKFF...",
    "...FFFFFFFFFF...",
    "...FFFFRRFFFF...",
    "....FFFFFFFF....",
    "....CCCCCCCC....",
    "...CCCCCCCCCC...",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "..FCCCCCCCCCCF..",
    "..F.CCCCCCCC.F..",
    "....DDDDDDDD....",
    "....DDDDDDDD....",
    "....DDD..DDD....",
    "....DD....DD....",
    "....DD....DD....",
    "...KKK....KKK...",
    "...KKK....KKK...",
  ];

  /* 歩き2フレーム(足だけ差し替え) */
  const HERO_WALK_A = HERO_STAND.slice(0, 16).concat([
    "...DDDD..DDDD...",
    "...DDD....DDD...",
    "..DDD......DDD..",
    ".KKK........KKK.",
    "................",
    "................",
  ]);
  const HERO_WALK_B = HERO_STAND.slice(0, 16).concat([
    ".....DDDDDD.....",
    ".....DDDDDD.....",
    "......DDDD......",
    ".....KKKKKK.....",
    "................",
    "................",
  ]);

  /* 万歳(腕上げ) */
  const HERO_BANZAI = [
    ".FF.HHHHHHHH.FF.",
    ".CCHHHHHHHHHHCC.",
    ".CHHHHHHHHHHHHC.",
    ".CHHFFFFFFFFHHC.",
    ".CHFFFFFFFFFFHC.",
    ".C.FFKKFFKKFF.C.",
    ".C.FFFFFFFFFF.C.",
    ".C.FFFRRRRFFF.C.",
    "....FFFFFFFF....",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "...CCCCCCCCCC...",
    "....CCCCCCCC....",
    "....CCCCCCCC....",
    "....DDDDDDDD....",
    "....DDDDDDDD....",
    "...DDDD..DDDD...",
    "...DD......DD...",
    "..DDD......DDD..",
    ".KKK........KKK.",
    "................",
  ];

  /* スーツ(白い襟 + 赤ネクタイ) */
  const HERO_SUIT = HERO_STAND.slice(0, 9).concat([
    "....CWWRRWWC....",
    "...CCCWRRWCCC...",
    "..CCCCCRRCCCCC..",
    "..CCCCCRRCCCCC..",
    "..FCCCCRRCCCCF..",
    "..F.CCCCCCCC.F..",
  ], HERO_STAND.slice(15));

  /* 敬礼(右手をおでこへ) */
  const HERO_SALUTE = [
    "....HHHHHHHH....",
    "...HHHHHHHHHH...",
    "..HHHHHHHHHHHH..",
    "..HHFFFFFFFFHHFF",
    "..HFFFFFFFFFFHF.",
    "...FFKKFFKKFFC..",
    "...FFFFFFFFFFC..",
    "...FFFFRRFFFFC..",
    "....FFFFFFFFC...",
    "....CWWRRWWCC...",
    "...CCCWRRWCCC...",
    "..CCCCCRRCCCC...",
    "..CCCCCRRCCCC...",
    "..FCCCCRRCCCC...",
    "..F.CCCCCCCC....",
    "....DDDDDDDD....",
    "....DDDDDDDD....",
    "....DDD..DDD....",
    "....DD....DD....",
    "....DD....DD....",
    "...KKK....KKK...",
    "...KKK....KKK...",
  ];

  /* がっくり(頭を落として肩を落とす) */
  const HERO_SAD = [
    "................",
    "................",
    "....HHHHHHHH....",
    "...HHHHHHHHHH...",
    "..HHHHHHHHHHHH..",
    "..HHHHHHHHHHHH..",
    "..HHFFFFFFFFHH..",
    "...FFFFFFFFFF...",
    "...FKKFFFFKKF...",
    "....FFFFFFFF....",
    "....CCCCCCCC....",
    "...CCCCCCCCCC...",
    "..CCCCCCCCCCCC..",
    ".CCCCCCCCCCCCCC.",
    ".FCCCCCCCCCCCCF.",
    ".F..CCCCCCCC..F.",
    "....DDDDDDDD....",
    "....DDDDDDDD....",
    "....DDD..DDD....",
    "....DD....DD....",
    "...KKK....KKK...",
    "...KKK....KKK...",
  ];

  /* 花嫁(16x22。白ドレス + ベール) */
  const BRIDE = [
    "....WWWWWWWW....",
    "...WWWWWWWWWW...",
    "..WWHHHHHHHHWW..",
    "..WHHFFFFFFHHW..",
    "..WHFFFFFFFFHW..",
    "..W.FKKFFKKF.W..",
    "..W.FFFFFFFF.W..",
    "..W.FFFRRFFF.W..",
    "....FFFFFFFF....",
    "....WWWWWWWW....",
    "...WWWWWWWWWW...",
    "..FWWWWWWWWWWF..",
    "..FWWWWWWWWWWF..",
    "..WWWWWWWWWWWW..",
    ".WWWWWWWWWWWWWW.",
    ".WWWWWWWWWWWWWW.",
    "WWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWW",
    "EWWEWWEWWEWWEWWE",
    "................",
    "...KK......KK...",
  ];

  /* 赤ちゃん(おくるみ 12x10)。P=おくるみ色 */
  const BABY = [
    "...PPPPPP...",
    "..PPPPPPPP..",
    ".PPFFFFFFPP.",
    ".PPFKFFKFPP.",
    ".PPFFFFFFPP.",
    ".PPFFRRFFPP.",
    ".PPPFFFFPPP.",
    ".PPPPPPPPPP.",
    "..PPPPPPPP..",
    "...PPPPPP...",
  ];

  /* 教会(24x22。十字架 + 三角屋根) */
  const CHURCH = [
    "...........YY...........",
    "..........YYYY..........",
    "...........YY...........",
    "...........YY...........",
    "..........KKKK..........",
    ".........RRRRRR.........",
    "........RRRRRRRR........",
    ".......RRRRRRRRRR.......",
    "......RRRRRRRRRRRR......",
    ".....RRRRRRRRRRRRRR.....",
    "....RRRRRRRRRRRRRRRR....",
    "...RRRRRRRRRRRRRRRRRR...",
    "...WWWWWWWWWWWWWWWWWW...",
    "...WWWWWWWBBBBWWWWWWW...",
    "...WWWWWWBBYYBBWWWWWW...",
    "...WWWWWWBBYYBBWWWWWW...",
    "...WWWWWWWBBBBWWWWWWW...",
    "...WWWWWWWWWWWWWWWWWW...",
    "...WWWWWWWNNNNWWWWWWW...",
    "...WWWWWWNNNNNNWWWWWW...",
    "...WWWWWWNNNNNNWWWWWW...",
    "...KKKKKKKKKKKKKKKKKK...",
  ];

  /* 家(24x14。赤屋根 + 白壁) */
  const HOUSE = [
    "........RRRRRRRR........",
    "......RRRRRRRRRRRR......",
    "....RRRRRRRRRRRRRRRR....",
    "..RRRRRRRRRRRRRRRRRRRR..",
    "RRRRRRRRRRRRRRRRRRRRRRRR",
    "KKKKKKKKKKKKKKKKKKKKKKKK",
    ".WWWWWWWWWWWWWWWWWWWWWW.",
    ".WWBBBBWWWWWWWWWWBBBBWW.",
    ".WWByBBWWWNNNNWWWByBBWW.",
    ".WWBBBBWWWNNNNWWWBBBBWW.",
    ".WWWWWWWWWNyNNWWWWWWWWW.",
    ".WWWWWWWWWNNNNWWWWWWWWW.",
    ".WWWWWWWWWNNNNWWWWWWWWW.",
    "KKKKKKKKKKKKKKKKKKKKKKKK",
  ];

  /* 車(22x11)。C=車体色 */
  const CAR = [
    "......KKKKKKK.........",
    ".....KbbbbbbbK........",
    "....KbbbKbbbbbK.......",
    "...KKKKKKKKKKKKK......",
    "..KCCCCCCCCCCCCKKKKK..",
    ".KCCCCCCCCCCCCCCCCCCK.",
    ".KCCCCCCCCCCCCCCCCCCK.",
    ".KKKKKKKKKKKKKKKKKKKK.",
    "...KssK........KssK...",
    "...KsWK........KsWK...",
    "....KK..........KK....",
  ];

  /* 岩(10x6) */
  const ROCK = [
    "...SSSS...",
    "..SSSSSS..",
    ".SSSSSSSs.",
    "SSSSSSSSSs",
    "SSSSSSSsss",
    "ssssssssss",
  ];

  /* 城(15x12。門は広め。scale 3 で描く) */
  const CASTLE2 = [
    "K.K.K.....K.K.K",
    "KKKKK.....KKKKK",
    "KWWWK.....KWWWK",
    "KWKWK.....KWKWK",
    "KWWWK.....KWWWK",
    "KWWWKKKKKKKWWWK",
    "KWWWWWWWWWWWWWK",
    "KWWKWNNNNNWKWWK",
    "KWWWWNNNNNWWWWK",
    "KWWWWNNNNNWWWWK",
    "KWWWWNNNNNWWWWK",
    "KKKKKKKKKKKKKKK",
  ];
  const FLAG_A = ["RRRR", "RRRR", "RR.."];
  const FLAG_B = ["RR..", "RRRR", "RRRR"];

  /* 炎(8x10 x 3フレーム) */
  const FLAME = [
    [
      "...O....",
      "...OO...",
      "..OOO...",
      "..OOOO..",
      ".OOOOO..",
      ".OOYYO..",
      "OOYYYYO.",
      "OYYWYYO.",
      "OYWWWYO.",
      ".OYYYO..",
    ],
    [
      "....O...",
      "...OO...",
      "...OOO..",
      "..OOOO..",
      "..OOOOO.",
      ".OOYYOO.",
      ".OYYYYO.",
      "OYYWWYO.",
      "OYWWWYO.",
      ".OYYYO..",
    ],
    [
      "..O.....",
      "..OO..O.",
      ".OOO.OO.",
      ".OOOOOO.",
      ".OOOOO..",
      "OOYYOO..",
      "OYYYYOO.",
      "OYWWYYO.",
      ".OYWWYO.",
      "..OYYO..",
    ],
  ];

  /* カラス(10x5 x 2フレーム) */
  const CROW_A = [
    ".KK.......",
    "..KKK.....",
    "..KKKKKKO.",
    ".KKKKKKKO.",
    "...KK.KK..",
  ];
  const CROW_B = [
    "..........",
    "..KKKKKKO.",
    ".KKKKKKKO.",
    ".KK..KK...",
    "..........",
  ];

  /* 小物 */
  const HEART = [
    ".RR.RR.",
    "RRRRRRR",
    "RRRRRRR",
    ".RRRRR.",
    "..RRR..",
    "...R...",
  ];
  const STAR = [
    "..Y..",
    ".YYY.",
    "YYYYY",
    ".YYY.",
    "..Y..",
  ];
  const SPARK = [
    "...W...",
    "...W...",
    "...W...",
    "WWWYWWW",
    "...W...",
    "...W...",
    "...W...",
  ];
  const COIN_A = [
    "..KKKK..",
    ".KYYYYK.",
    "KYWYYYYK",
    "KYYYYYYK",
    "KYYYYYYK",
    "KYYYYOYK",
    ".KYYYYK.",
    "..KKKK..",
  ];
  const COIN_B = [
    "...KK...",
    "..KYYK..",
    "..KYYK..",
    "..KYYK..",
    "..KYYK..",
    "..KYYK..",
    "..KYYK..",
    "...KK...",
  ];

  /* 「?」「!」(ブロックの中身) */
  const QMARK = [
    ".KKKK.",
    "KK..KK",
    "KK..KK",
    "...KK.",
    "..KK..",
    "..KK..",
    "......",
    "..KK..",
    "..KK..",
  ];
  const EMARK = [
    ".KK.",
    ".KK.",
    ".KK.",
    ".KK.",
    ".KK.",
    ".KK.",
    "....",
    ".KK.",
    ".KK.",
  ];

  /* =========================================================
   * 描画ヘルパー
   * =======================================================*/

  /* テキストグリッドを 1文字=1ドット(scale倍)で描く */
  function sp(ctx, rows, x, y, pal, scale) {
    const s = scale || 1;
    for (let j = 0; j < rows.length; j++) {
      const row = rows[j];
      for (let i = 0; i < row.length; i++) {
        const ch = row[i];
        if (ch === ".") continue;
        ctx.fillStyle = (pal && pal[ch]) || C[ch] || "#f0f";
        ctx.fillRect(x + i * s, y + j * s, s, s);
      }
    }
  }

  /* 色の明暗 */
  function shade(hex, k) {
    const n = parseInt(hex.slice(1), 16);
    const f = (v) => Math.max(0, Math.min(255, Math.round(v * k)));
    return `rgb(${f(n >> 16)},${f((n >> 8) & 255)},${f(n & 255)})`;
  }

  /* 主人公の服パレット */
  function heroPal(color) {
    const c = color || "#e23b3b";
    return { C: c, D: shade(c, 0.6) };
  }

  /* 補間・イージング */
  const lerp = (a, b, k) => a + (b - a) * k;
  const clamp01 = (v) => Math.max(0, Math.min(1, v));
  /* k を区間 [a,b] 内の進行度 0..1 に写す(キーフレーム進行) */
  const seg = (k, a, b) => clamp01((k - a) / (b - a));
  const easeOut = (k) => 1 - (1 - k) * (1 - k);
  function easeOutBack(k) {
    const c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
  }

  /* 空 + 地面 */
  function sky(ctx, top, ground, gy) {
    ctx.fillStyle = top;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = ground;
    ctx.fillRect(0, gy, W, H - gy);
    ctx.fillStyle = shade(ground, 1.25);
    ctx.fillRect(0, gy, W, 1);
  }

  /* 足元の影 */
  function shadow(ctx, cx, y, w) {
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fillRect(cx - ((w || 12) >> 1), y, w || 12, 2);
  }

  /* 紙吹雪(種固定で毎回同じ散り方。k で落ちる) */
  function confetti(ctx, k) {
    const cols = [C.Y, C.W, C.P, "#58b0e8", C.R];
    for (let i = 0; i < 22; i++) {
      const x = Math.round(RND[i] * (W - 8) + 4);
      const fall = (RND[i + 22] + k * (0.7 + RND[i + 44] * 0.6)) % 1;
      const y = Math.round(fall * (H + 8) - 4);
      ctx.fillStyle = cols[i % cols.length];
      ctx.fillRect(x, y, i % 3 === 0 ? 1 : 2, 1);
    }
  }

  /* 花火(kk: 0→1 で開く。1 で満開のまま止まる) */
  function firework(ctx, cx, cy, kk, color) {
    if (kk <= 0) return;
    const r = 3 + kk * 20;
    const cols = [color, C.Y, C.W];
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      const x = Math.round(cx + Math.cos(a) * r);
      const y = Math.round(cy + Math.sin(a) * r * 0.85);
      ctx.fillStyle = cols[i % 3];
      const d = kk < 0.6 ? 2 : 1;   // 開ききると小さく消えかける
      ctx.fillRect(x, y, d, d);
    }
    if (kk < 0.25) {                 // 打ち上げ直後の中心の閃光
      ctx.fillStyle = C.W;
      ctx.fillRect(cx - 1, cy - 1, 3, 3);
    }
  }

  /* ビル(灰色 + 窓明かり。窓の点灯は種固定) */
  function bldg(ctx, x, y, w, h, body) {
    ctx.fillStyle = C.K;
    ctx.fillRect(x - 1, y - 1, w + 2, h + 2);
    ctx.fillStyle = body;
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = shade(body, 1.25);
    ctx.fillRect(x, y, w, 2);
    let idx = x + y;
    for (let wy = y + 5; wy < y + h - 5; wy += 8) {
      for (let wx = x + 4; wx < x + w - 6; wx += 8) {
        ctx.fillStyle = RND[(idx++) % 96] < 0.3 ? "#3a4050" : C.Y;
        ctx.fillRect(wx, wy, 4, 5);
      }
    }
  }

  /* 保険証書(青い額縁 + 本文の線 + 赤い判子) */
  function drawCert(ctx, x, y, w, h) {
    ctx.fillStyle = C.K;
    ctx.fillRect(x - 4, y - 4, w + 8, h + 8);
    ctx.fillStyle = C.B;
    ctx.fillRect(x - 3, y - 3, w + 6, h + 6);
    ctx.fillStyle = C.W;
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#a8b4d0";                    // 飾り罫
    ctx.fillRect(x + 3, y + 3, w - 6, 1);
    ctx.fillRect(x + 3, y + h - 4, w - 6, 1);
    ctx.fillRect(x + 3, y + 3, 1, h - 6);
    ctx.fillRect(x + w - 4, y + 3, 1, h - 6);
    ctx.fillStyle = "#38486a";                    // 題字(太線)
    ctx.fillRect(x + (w >> 1) - 16, y + 8, 32, 4);
    ctx.fillStyle = "#98a0b0";                    // 本文の線
    for (let ly = y + 18; ly < y + h - 12; ly += 6) {
      ctx.fillRect(x + 8, ly, w - 16, 2);
    }
    ctx.fillStyle = C.R;                          // 判子
    ctx.fillRect(x + w - 18, y + h - 16, 10, 10);
    ctx.fillStyle = "#f8b0a8";
    ctx.fillRect(x + w - 16, y + h - 14, 6, 6);
    ctx.fillStyle = C.R;
    ctx.fillRect(x + w - 15, y + h - 13, 4, 4);
  }

  /* ?ブロック(30x30。boom で「!」に変わる) */
  function drawBlock(ctx, x, y, s, boom) {
    ctx.fillStyle = C.K;
    ctx.fillRect(x - 2, y - 2, s + 4, s + 4);
    ctx.fillStyle = boom ? C.O : C.Y;
    ctx.fillRect(x, y, s, s);
    ctx.fillStyle = boom ? "#f8a850" : C.y;       // 左上ハイライト
    ctx.fillRect(x, y, s, 2);
    ctx.fillRect(x, y, 2, s);
    ctx.fillStyle = boom ? "#a04810" : "#c8a018"; // 右下の影
    ctx.fillRect(x, y + s - 2, s, 2);
    ctx.fillRect(x + s - 2, y, 2, s);
    ctx.fillStyle = C.K;                          // 四隅のリベット
    for (const [rx, ry] of [[3, 3], [s - 5, 3], [3, s - 5], [s - 5, s - 5]]) {
      ctx.fillRect(x + rx, y + ry, 2, 2);
    }
    if (boom) {
      sp(ctx, EMARK, x + ((s - 12) >> 1), y + ((s - 27) >> 1), { K: C.W }, 3);
    } else {
      sp(ctx, QMARK, x + ((s - 12) >> 1), y + ((s - 18) >> 1), null, 2);
    }
  }

  /* =========================================================
   * シーン定義
   * 各 draw(ctx, k, t, o):
   *   k = キーフレーム進行度 0→1(fast でも同じ 0→1)
   *   t = 経過ミリ秒(パラパラ用。reduced-motion 時は常に 0)
   *   o = play() の opts
   * =======================================================*/

  const DEFS = {

    /* ---- 1. 結婚:教会の前でふたり並び、ハートと紙吹雪 ---- */
    marry: {
      label: "ケッコン!",
      draw(ctx, k, t, o) {
        sky(ctx, "#8fd4f0", "#2f8a3f", 92);
        sp(ctx, CHURCH, 72, 92 - 44, null, 2);
        // ふたりが左右から歩み寄る(k 0→0.45)
        const pk = easeOut(seg(k, 0, 0.45));
        const hx = Math.round(lerp(24, 74, pk));
        const bx = Math.round(lerp(166, 116, pk));
        const walking = pk < 1;
        const hr = walking ? (Math.floor(t / 110) % 2 ? HERO_WALK_A : HERO_WALK_B) : HERO_STAND;
        shadow(ctx, hx + 8, 104);
        shadow(ctx, bx + 8, 104);
        sp(ctx, hr, hx, 104 - 22, heroPal(o.color));
        sp(ctx, BRIDE, bx, 104 - 22);
        // ハート3つがふわっと浮かぶ(k 0.5→)
        const hk = seg(k, 0.5, 0.9);
        if (hk > 0) {
          for (let i = 0; i < 3; i++) {
            const hy = 56 - hk * 16 + Math.sin(t / 160 + i * 2.1) * 2 + (i === 1 ? -7 : 0);
            sp(ctx, HEART, 84 + (i - 1) * 20, Math.round(hy));
          }
        }
        if (k > 0.5) confetti(ctx, seg(k, 0.5, 1));
      },
    },

    /* ---- 2. 出産:おくるみの赤ちゃんがぴょこぴょこ ---- */
    baby: {
      label: "タンジョウ!",
      draw(ctx, k, t, o) {
        ctx.fillStyle = "#f8dce6";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "#e8c0d0";               // 水玉の壁紙
        for (let i = 0; i < 18; i++) {
          ctx.fillRect(Math.round(RND[i] * W), Math.round(RND[i + 18] * 84), 2, 2);
        }
        ctx.fillStyle = "#d8a8bc";               // 床
        ctx.fillRect(0, 94, W, H - 94);
        // 赤ちゃん(count 人。跳ねは k で 3 回) */
        const n = Math.max(1, Math.min(3, o.count || 1));
        const x0 = (W - (n * 24 + (n - 1) * 12)) >> 1;
        for (let i = 0; i < n; i++) {
          const bob = -Math.abs(Math.sin(k * Math.PI * 3 + i * 0.9)) * 8;
          const bx = x0 + i * 36;
          shadow(ctx, bx + 12, 94, 16);
          sp(ctx, BABY, bx, 94 - 20 + Math.round(bob), i % 2 ? { P: "#90c0f0" } : null, 2);
        }
        // まわりのキラキラ
        for (let i = 0; i < 4; i++) {
          if (Math.floor(t / 150 + i) % 3 === 0) continue;
          sp(ctx, STAR, [22, 158, 40, 142][i], [30, 36, 66, 62][i], { Y: C.W });
        }
      },
    },

    /* ---- 3. マイホーム:家が下からドーンとせり上がる ---- */
    house: {
      label: "マイホーム!",
      draw(ctx, k, t) {
        sky(ctx, "#8fd4f0", "#2f8a3f", 96);
        const hk = easeOutBack(seg(k, 0, 0.65));
        const hy = Math.round(lerp(H + 4, 96 - 42, hk));
        sp(ctx, HOUSE, 60, hy, null, 3);
        // せり上がり中の土煙
        if (k > 0.04 && k < 0.7) {
          ctx.fillStyle = "#c8bca0";
          for (let i = 0; i < 6; i++) {
            const px = 56 + i * 16 + Math.round(Math.sin(t / 90 + i) * 2);
            const py = 96 - Math.round(seg(k, 0, 0.65) * 6 + (i % 2) * 3);
            ctx.fillRect(px, py, 3, 2);
          }
        }
        // 完成後のキラキラ
        if (k > 0.6) {
          for (let i = 0; i < 4; i++) {
            if (Math.floor(t / 140 + i) % 3 === 0) continue;
            sp(ctx, SPARK, [40, 140, 66, 116][i], [34, 40, 18, 22][i]);
          }
        }
      },
    },

    /* ---- 4. 火事:家から炎と煙、画面が赤く点滅 ---- */
    fire: {
      label: "カジだー!",
      draw(ctx, k, t) {
        sky(ctx, "#402830", "#3a3028", 96);
        sp(ctx, HOUSE, 60, 96 - 42, null, 3);
        // 炎(3フレームでゆらめき、k で燃え広がる)
        const fr = Math.floor(t / 110) % 3;
        const g = seg(k, 0, 0.4);
        if (g > 0.15) {                          // 窓から
          sp(ctx, FLAME[fr], 66, 78 - 10, null, 1);
          sp(ctx, FLAME[(fr + 1) % 3], 108, 78 - 10, null, 1);
        }
        if (g > 0.55) {                          // 屋根の上に大炎
          sp(ctx, FLAME[(fr + 2) % 3], 78, 54 - 20 + 4, null, 2);
        }
        // 煙(灰色の塊が立ちのぼる)
        ctx.fillStyle = "rgba(150,150,150,0.8)";
        for (let i = 0; i < 3; i++) {
          const sy = 44 - ((t * 0.03 + i * 14 + k * 20) % 36);
          const sx2 = 88 + i * 8 + Math.round(Math.sin(t / 300 + i) * 3);
          ctx.fillRect(sx2, Math.round(sy), 5, 4);
          ctx.fillRect(sx2 + 2, Math.round(sy) - 3, 3, 3);
        }
        // 画面が赤っぽく点滅
        if (Math.floor(t / 160) % 2 === 0) {
          ctx.fillStyle = "rgba(216,48,40,0.16)";
          ctx.fillRect(0, 0, W, H);
        }
      },
    },

    /* ---- 5. 事故:車がスリップして岩に衝突、星チカチカ + シェイク ---- */
    accident: {
      label: "ジコ!",
      draw(ctx, k, t, o) {
        // 衝突後は canvas 内でシェイク
        let sx = 0, sy = 0;
        if (k >= 0.5 && k < 0.95) {
          const p = 1 - seg(k, 0.5, 0.95);
          sx = Math.round(Math.sin(t * 0.7) * 3 * p);
          sy = Math.round(Math.cos(t * 0.9) * 2 * p);
        }
        ctx.save();
        ctx.translate(sx, sy);
        sky(ctx, "#88b8d8", "#2f8a3f", 64);
        ctx.fillStyle = "#585c66";               // 道路
        ctx.fillRect(0, 72, W, 32);
        ctx.fillStyle = C.W;                     // 車線
        for (let x = 4; x < W; x += 20) ctx.fillRect(x, 87, 9, 2);
        sp(ctx, ROCK, 148, 92 - 12, null, 2);    // 障害物の岩
        // 車が左から突っ込む(k 0→0.5)
        const ck = easeOut(seg(k, 0, 0.5));
        const cx = Math.round(lerp(-48, 108, ck));
        if (ck > 0.25) {                         // スリップ痕
          ctx.fillStyle = "#23262c";
          ctx.fillRect(24, 90, cx - 14, 2);
          ctx.fillRect(30, 94, cx - 24, 2);
        }
        sp(ctx, CAR, cx, 92 - 22, { C: (o.color || C.R), D: shade(o.color || C.R, 0.6) }, 2);
        // 衝突の星チカチカ
        if (k >= 0.5) {
          for (let i = 0; i < 4; i++) {
            if (Math.floor(t / 90 + i) % 2 !== 0) continue;
            const a = t / 260 + i * 1.6;
            const px = 152 + Math.round(Math.cos(a) * 15);
            const py = 66 + Math.round(Math.sin(a) * 9);
            sp(ctx, STAR, px, py);
          }
          ctx.fillStyle = C.W;                   // 衝撃線
          ctx.fillRect(146, 56, 2, 6);
          ctx.fillRect(158, 54, 2, 8);
          ctx.fillRect(168, 60, 6, 2);
        }
        ctx.restore();
      },
    },

    /* ---- 6. 保険:証書がキラーンと光る(光線が回転) ---- */
    saved: {
      label: "ホケンが おりた!",
      draw(ctx, k, t) {
        ctx.fillStyle = "#243878";
        ctx.fillRect(0, 0, W, H);
        // 回転する放射光
        ctx.save();
        ctx.translate(96, 52);
        const a0 = t * 0.0022;
        for (let i = 0; i < 12; i++) {
          const a1 = a0 + (i * Math.PI) / 6;
          const a2 = a1 + 0.18;
          ctx.fillStyle = i % 2 ? "rgba(248,216,56,0.22)" : "rgba(248,248,240,0.10)";
          ctx.beginPath();
          ctx.moveTo(0, 0);
          ctx.lineTo(Math.cos(a1) * 150, Math.sin(a1) * 150);
          ctx.lineTo(Math.cos(a2) * 150, Math.sin(a2) * 150);
          ctx.fill();
        }
        ctx.restore();
        // 証書が上からストンと落ちてくる(k 0.1→0.5)
        const pk = easeOutBack(seg(k, 0.1, 0.5));
        drawCert(ctx, 52, Math.round(lerp(-70, 24, pk)), 88, 56);
        // キラーン(白い十字の光が斜めに走る)
        const skk = seg(k, 0.55, 0.9);
        if (skk > 0 && skk < 1) {
          const gx = Math.round(lerp(58, 130, skk));
          const gy = Math.round(lerp(30, 70, skk));
          const gs = Math.round(Math.sin(skk * Math.PI) * 6) + 2;
          ctx.fillStyle = C.W;
          ctx.fillRect(gx - gs, gy, gs * 2 + 1, 1);
          ctx.fillRect(gx, gy - gs, 1, gs * 2 + 1);
          ctx.fillStyle = C.Y;
          ctx.fillRect(gx - 1, gy - 1, 3, 3);
        }
      },
    },

    /* ---- 7. 就職:ビル街でネクタイ姿がビシッと敬礼 ---- */
    job: {
      label: "シューショク!",
      draw(ctx, k, t, o) {
        sky(ctx, "#78c0f0", "#787c88", 92);
        bldg(ctx, 14, 22, 44, 70, "#8890a0");
        bldg(ctx, 132, 34, 46, 58, "#6a7284");
        // k 0.45 で「気をつけ」→「敬礼」に切り替え
        const sal = k >= 0.45;
        const rows = sal ? HERO_SALUTE : HERO_SUIT;
        shadow(ctx, 96, 102);
        sp(ctx, rows, 88, 102 - 22, heroPal(o.color));
        // 敬礼と同時に集中線(サラリーマン誕生の勢い)
        if (sal && Math.floor(t / 110) % 2 === 0) {
          ctx.strokeStyle = "rgba(248,248,240,0.85)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          for (let i = 0; i < 14; i++) {
            const a = (i / 14) * Math.PI * 2 + 0.22;
            ctx.moveTo(96 + Math.cos(a) * 120, 62 + Math.sin(a) * 86);
            ctx.lineTo(96 + Math.cos(a) * 64, 62 + Math.sin(a) * 48);
          }
          ctx.stroke();
        }
      },
    },

    /* ---- 8. ゴール:城門が開いて入城、花火2発 ---- */
    goal: {
      label: "ゴール!",
      draw(ctx, k, t, o) {
        ctx.fillStyle = "#1c2c58";               // 夕暮れの空
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = C.W;                     // 星
        for (let i = 0; i < 12; i++) {
          if (Math.floor(t / 380 + i) % 4 === 0) continue;
          ctx.fillRect(Math.round(RND[i] * W), Math.round(RND[i + 12] * 48), 1, 1);
        }
        ctx.fillStyle = "#24623a";               // 地面
        ctx.fillRect(0, 92, W, H - 92);
        // 城(scale 3)と旗
        const cy = 92 - 36;
        sp(ctx, CASTLE2, 73, cy, null, 3);
        const flag = Math.floor(t / 320) % 2 === 0 ? FLAG_A : FLAG_B;
        for (const fx of [79, 112]) {
          ctx.fillStyle = C.K;
          ctx.fillRect(fx, cy - 8, 2, 8);
          sp(ctx, flag, fx + 2, cy - 8, null, 2);
        }
        // 門が左右に開く(k 0→0.3)
        const gk = easeOut(seg(k, 0, 0.3));
        ctx.fillStyle = "#100c08";               // 開いた奥の暗闇
        ctx.fillRect(88, cy + 21, 15, 12);
        ctx.fillStyle = C.N;                     // 左右の扉
        ctx.fillRect(88, cy + 21, Math.round(8 * (1 - gk)), 12);
        const rw = Math.round(7 * (1 - gk));
        ctx.fillRect(88 + 15 - rw, cy + 21, rw, 12);
        // 主人公が歩いて入っていく(k 0.15→0.7。門に入ると消える)
        const wk = seg(k, 0.15, 0.7);
        const alpha = 1 - seg(k, 0.6, 0.72);
        if (alpha > 0) {
          const fy = Math.round(lerp(110, 90, wk));
          const rows = wk < 1 ? (Math.floor(t / 110) % 2 ? HERO_WALK_A : HERO_WALK_B) : HERO_STAND;
          ctx.globalAlpha = alpha;
          shadow(ctx, 96, fy);
          sp(ctx, rows, 88, fy - 22, heroPal(o.color));
          ctx.globalAlpha = 1;
        }
        // 花火2発
        firework(ctx, 42, 28, seg(k, 0.5, 0.85), o.color || "#f088a8");
        firework(ctx, 150, 22, seg(k, 0.68, 1.05), C.Y);
      },
    },

    /* ---- 9. 大当たり:コインの雨の中で万歳 ---- */
    win: {
      label: "オオアタリ!",
      draw(ctx, k, t, o) {
        ctx.fillStyle = "#284070";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "#3a5890";
        ctx.fillRect(0, 96, W, H - 96);
        // 主人公:途中から万歳して跳ねる
        const rows = k < 0.25 ? HERO_STAND : HERO_BANZAI;
        const bob = k >= 0.25 ? -Math.round(Math.abs(Math.sin(t / 140)) * 3) : 0;
        shadow(ctx, 96, 104);
        sp(ctx, rows, 88, 104 - 22 + bob, heroPal(o.color));
        // コインがジャラジャラ降る(種固定 + くるくる回転)
        for (let i = 0; i < 18; i++) {
          const x = Math.round(RND[i] * (W - 12) + 2);
          const fall = (RND[i + 18] + k * (1.0 + RND[i + 36] * 0.6)) % 1;
          const y = Math.round(fall * (H + 16) - 8);
          const coin = Math.floor(t / 90 + i) % 2 ? COIN_B : COIN_A;
          sp(ctx, coin, x, y);
        }
      },
    },

    /* ---- 10. ハズレ:がっくりうなだれ、頭上をカラスが横切る ---- */
    lose: {
      label: "ハズレ…",
      draw(ctx, k, t, o) {
        sky(ctx, "#2c3038", "#3c4048", 92);
        ctx.fillStyle = "#222630";               // どんよりした雲
        ctx.fillRect(18, 14, 44, 7);
        ctx.fillRect(120, 22, 52, 7);
        // 主人公:途中でがっくり
        const rows = k < 0.3 ? HERO_STAND : HERO_SAD;
        shadow(ctx, 96, 102);
        sp(ctx, rows, 88, 102 - 22, heroPal(o.color));
        // 冷や汗
        if (k > 0.4 && Math.floor(t / 300) % 2 === 0) {
          ctx.fillStyle = C.b;
          ctx.fillRect(103, 86, 2, 3);
        }
        // 「…」が順に出る
        for (let d = 0; d < 3; d++) {
          if (k > 0.45 + d * 0.12) {
            ctx.fillStyle = C.W;
            ctx.fillRect(106 + d * 5, 68, 2, 2);
          }
        }
        // カラスが1羽横切る
        const crow = Math.floor(t / 130) % 2 ? CROW_A : CROW_B;
        const cx = Math.round(lerp(-14, 200, k));
        const cyr = 26 + Math.round(Math.sin(k * 9) * 3);
        sp(ctx, crow, cx, cyr, { O: C.O });
      },
    },

    /* ---- 11. ハプニング:「?」ブロックが震えて「!」に ---- */
    happen: {
      label: "ナニカが おこった!",
      draw(ctx, k, t) {
        ctx.fillStyle = "#202030";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "#2c2c44";               // 市松の床
        for (let x = 0; x < W; x += 16) {
          for (let y = 88; y < H; y += 8) {
            if (((x + y) / 8) % 2 === 0) ctx.fillRect(x, y, 16, 8);
          }
        }
        const boom = k >= 0.55;
        // 震え(「!」になったら止まる)
        const dx = boom ? 0 : Math.round(Math.sin(t * 0.09) * 2);
        const dy = boom ? 0 : Math.round(Math.cos(t * 0.13) * 1);
        drawBlock(ctx, 81 + dx, 34 + dy, 30, boom);
        shadow(ctx, 96, 70, 26);
        if (boom) {
          // 変化の瞬間に白いリングが広がる
          const rk = seg(k, 0.55, 1);
          if (rk < 1) {
            ctx.strokeStyle = `rgba(248,248,240,${(1 - rk).toFixed(2)})`;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(96, 49, 6 + rk * 66, 0, Math.PI * 2);
            ctx.stroke();
          }
          for (let i = 0; i < 4; i++) {          // まわりの星
            if (Math.floor(t / 120 + i) % 2 !== 0) continue;
            sp(ctx, STAR, [56, 128, 66, 118][i], [22, 26, 62, 58][i]);
          }
        }
      },
    },
  };

  /* =========================================================
   * オーバーレイ本体
   * =======================================================*/

  const CSS = `
#scn-overlay{position:fixed;inset:0;z-index:2000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.55);cursor:pointer;}
#scn-overlay.scn-hidden{display:none;}
#scn-overlay .scn-window{background:#fdf8e6;border:6px solid #f0c419;border-radius:6px;box-shadow:0 0 0 3px #181008,0 12px 24px rgba(0,0,0,0.5);padding:12px 12px 8px;text-align:center;}
#scn-canvas{display:block;width:min(520px,92vw);height:auto;image-rendering:pixelated;image-rendering:crisp-edges;background:#181008;border:3px solid #181008;}
#scn-label{font:inherit;font-size:clamp(20px,5vw,32px);letter-spacing:0.14em;color:#181008;margin-top:8px;line-height:1.2;}
#scn-overlay .scn-hint{font:inherit;font-size:11px;color:#9a8a5a;margin-top:2px;letter-spacing:0.1em;}
`;

  const Scn = {
    _root: null,
    _canvas: null,
    _ctx: null,
    _label: null,
    _active: null,     // 再生中の状態 {def, opts, resolve, dur, hold, reduced, t0}
    _raf: 0,
    _mq: null,

    /* オーバーレイ DOM と CSS を注入して隠しておく(2回呼ばれても安全) */
    init() {
      if (this._root) return;
      const style = document.createElement("style");
      style.textContent = CSS;
      document.head.appendChild(style);

      const root = document.createElement("div");
      root.id = "scn-overlay";
      root.className = "scn-hidden";
      root.innerHTML =
        '<div class="scn-window">' +
        '<canvas id="scn-canvas" width="' + W + '" height="' + H + '"></canvas>' +
        '<div id="scn-label"></div>' +
        '<div class="scn-hint">クリックで とばす</div>' +
        "</div>";
      document.body.appendChild(root);

      this._root = root;
      this._canvas = root.querySelector("#scn-canvas");
      this._ctx = this._canvas.getContext("2d");
      this._ctx.imageSmoothingEnabled = false;
      this._label = root.querySelector("#scn-label");
      this._mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

      // クリック / タップでスキップ
      root.addEventListener("pointerdown", () => this._end());
    },

    /* カットインを再生。終わったら(またはクリックで)resolve */
    play(name, opts) {
      this.init();
      const o = opts || {};
      // 二重呼び対策:前の再生が残っていたら即終わらせてから始める
      if (this._active) this._end();

      const def = DEFS[name] || DEFS.happen;
      const reduced = !!(this._mq && this._mq.matches);
      // reduced-motion 時は静止画(k=1 固定)を短時間だけ見せる
      const dur = reduced ? 0 : (o.fast ? DUR_FAST : DUR_NORMAL);
      const hold = reduced ? 700 : (o.fast ? HOLD_FAST : HOLD_NORMAL);

      this._label.textContent = o.label || def.label;
      this._root.classList.remove("scn-hidden");

      // ジングル(Snd があれば。無くても動く)
      if (typeof Snd !== "undefined" && Snd && typeof Snd.jingle === "function") {
        try { Snd.jingle(name); } catch (e) { /* 音は失敗しても演出は続ける */ }
      }

      return new Promise((resolve) => {
        this._active = { def, opts: o, resolve, dur, hold, reduced, t0: performance.now() };
        cancelAnimationFrame(this._raf);
        const loop = (now) => {
          const a = this._active;
          if (!a) return;
          const el = now - a.t0;
          const k = a.dur <= 0 ? 1 : Math.min(1, el / a.dur);
          this._render(a, k, a.reduced ? 0 : el);
          if (el >= a.dur + a.hold) {
            this._end();
            return;
          }
          this._raf = requestAnimationFrame(loop);
        };
        this._raf = requestAnimationFrame(loop);
      });
    },

    /* 1フレーム描く */
    _render(a, k, t) {
      const ctx = this._ctx;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalAlpha = 1;
      ctx.imageSmoothingEnabled = false;
      ctx.fillStyle = C.K;
      ctx.fillRect(0, 0, W, H);
      a.def.draw(ctx, k, t, a.opts);
    },

    /* 終了(自動 or クリック)。オーバーレイを隠して resolve */
    _end() {
      const a = this._active;
      if (!a) return;
      this._active = null;
      cancelAnimationFrame(this._raf);
      this._root.classList.add("scn-hidden");
      a.resolve();
    },
  };

  return Scn;
})();
