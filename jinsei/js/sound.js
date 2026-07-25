/* =========================================================
 * 人生モドキ サウンドエンジン
 * WebAudio によるファミコン風チップチューン合成
 * (矩形波2ch+三角波+ノイズ。外部アセットなし)
 *
 * 使い方:
 *   Snd.init()        … 初回ユーザー操作時に呼ぶ(2回目以降は resume)
 *   Snd.sfx('coin')   … 短い効果音
 *   Snd.jingle('goal')… 短いメロディ(前のジングルは自動停止)
 *   Snd.setMuted(true)… ミュート
 * ========================================================= */

const Snd = (() => {

  let ctx = null;        // AudioContext(init まで null)
  let master = null;     // 全体音量
  let jingleNodes = [];  // 再生中ジングルのノード一覧(次のジングルで stop)

  const MASTER_VOL = 0.12;

  /* ---------- 内部ヘルパー ---------- */

  // AudioContext が眠っていたら起こす
  function wake() {
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
  }

  // 再生可能か
  function ready() {
    return !!ctx && !Snd.muted;
  }

  // 矩形波 1 音。track に push すると後で stop できる
  // freq:周波数 start:ctx.currentTime からの相対秒 dur:長さ duty:デューティ比 vol:音量
  function pulse(freq, start, dur, duty, vol, track) {
    const t0 = ctx.currentTime + start;
    const osc = ctx.createOscillator();
    // PeriodicWave でデューティ比つき矩形波を作る
    osc.setPeriodicWave(dutyWave(duty));
    osc.frequency.setValueAtTime(freq, t0);
    const g = ctx.createGain();
    env(g.gain, t0, dur, vol);
    osc.connect(g).connect(master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
    if (track) track.push(osc);
    return osc;
  }

  // 三角波 1 音(ベース用)
  function tri(freq, start, dur, vol, track) {
    const t0 = ctx.currentTime + start;
    const osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(freq, t0);
    const g = ctx.createGain();
    env(g.gain, t0, dur, vol);
    osc.connect(g).connect(master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
    if (track) track.push(osc);
    return osc;
  }

  // ノイズ 1 発(パーカッション用)
  function noise(start, dur, vol, track) {
    const t0 = ctx.currentTime + start;
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer();
    src.loop = true;
    const g = ctx.createGain();
    env(g.gain, t0, dur, vol);
    src.connect(g).connect(master);
    src.start(t0);
    src.stop(t0 + dur + 0.02);
    if (track) track.push(src);
    return src;
  }

  // 周波数スライドつき矩形波(効果音用)
  function sweep(f0, f1, start, dur, duty, vol, track) {
    const t0 = ctx.currentTime + start;
    const osc = ctx.createOscillator();
    osc.setPeriodicWave(dutyWave(duty));
    osc.frequency.setValueAtTime(f0, t0);
    osc.frequency.exponentialRampToValueAtTime(Math.max(1, f1), t0 + dur);
    const g = ctx.createGain();
    env(g.gain, t0, dur, vol);
    osc.connect(g).connect(master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
    if (track) track.push(osc);
    return osc;
  }

  // 短いアタック+ディケイのエンベロープ(クリックノイズ防止)
  function env(param, t0, dur, vol) {
    param.setValueAtTime(0.0001, t0);
    param.linearRampToValueAtTime(vol, t0 + 0.005);
    param.setValueAtTime(vol, t0 + Math.max(0.005, dur * 0.4));
    param.exponentialRampToValueAtTime(0.0001, t0 + dur);
  }

  // デューティ比つき矩形波の PeriodicWave(キャッシュ)
  const waveCache = {};
  function dutyWave(duty) {
    const key = String(duty);
    if (waveCache[key]) return waveCache[key];
    const N = 32;
    const real = new Float32Array(N);
    const imag = new Float32Array(N);
    for (let n = 1; n < N; n++) {
      // duty 比 d の矩形波のフーリエ係数
      real[n] = (2 / (n * Math.PI)) * Math.sin(n * Math.PI * duty);
    }
    waveCache[key] = ctx.createPeriodicWave(real, imag, { disableNormalization: false });
    return waveCache[key];
  }

  // ホワイトノイズバッファ(1 回だけ生成)
  let _noiseBuf = null;
  function noiseBuffer() {
    if (_noiseBuf) return _noiseBuf;
    const len = Math.floor(ctx.sampleRate * 0.2);
    _noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = _noiseBuf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    return _noiseBuf;
  }

  // 再生中ジングルを止める
  function stopJingle() {
    for (const n of jingleNodes) {
      try { n.stop(); } catch (e) { /* 既に停止済みなら無視 */ }
    }
    jingleNodes = [];
  }

  /* ---------- 音名 → 周波数 ---------- */
  // 'C4' 'F#5' 'Bb3' のような表記を周波数に変換
  const NOTE_IDX = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  function nf(name) {
    const m = /^([A-G])([#b]?)(\d)$/.exec(name);
    if (!m) return 440;
    let idx = NOTE_IDX[m[1]];
    if (m[2] === '#') idx++;
    if (m[2] === 'b') idx--;
    const oct = +m[3];
    return 440 * Math.pow(2, (idx - 9) / 12 + (oct - 4));
  }

  /* ---------- 効果音定義 ---------- */

  const SFX = {
    // ルーレットのカチ音:超短い高音ノイズ
    tick() {
      noise(0, 0.03, 0.5);
      pulse(2400, 0, 0.02, 0.5, 0.15);
    },
    // 決定:ピコッ(2音上昇)
    decide() {
      pulse(nf('E5'), 0,    0.06, 0.25, 0.6);
      pulse(nf('A5'), 0.06, 0.09, 0.25, 0.6);
    },
    // メッセージ送り:1音ビープ
    msgbeep() {
      pulse(nf('B5'), 0, 0.07, 0.5, 0.45);
    },
    // 文字送り:ごく短く控えめ(連打対応)
    typebeep() {
      pulse(nf('E6'), 0, 0.025, 0.5, 0.12);
    },
    // お金ゲット:ピロリン上昇
    coin() {
      pulse(nf('B5'), 0,    0.05, 0.5, 0.55);
      pulse(nf('E6'), 0.05, 0.10, 0.5, 0.55);
    },
    // 支払い:下降2音
    pay() {
      pulse(nf('A4'), 0,    0.07, 0.5, 0.5);
      pulse(nf('E4'), 0.07, 0.08, 0.5, 0.5);
    },
    // コマが跳ねる:ポッ(短い上昇スイープ)
    hop() {
      sweep(300, 700, 0, 0.07, 0.5, 0.45);
    },
    // ボタン押下:コッ(低い短音+微ノイズ)
    click() {
      pulse(nf('A3'), 0, 0.035, 0.5, 0.4);
      noise(0, 0.02, 0.2);
    },
  };

  /* ---------- ジングル定義 ----------
   * 各エントリは音符データの配列。
   *   ['p', 音名, 開始, 長さ, duty, 音量]  … 矩形波
   *   ['t', 音名, 開始, 長さ, 音量]        … 三角波(ベース)
   *   ['n', 開始, 長さ, 音量]              … ノイズ
   * すべてオリジナルの短いフレーズ。
   */

  const JINGLES = {

    // ゲーム開始:明るいファンファーレ(主旋律+3度下ハモリ+三角波ベース)1.2秒
    start: [
      ['p','C5',0.00,0.12,0.25,0.5], ['p','C5',0.15,0.12,0.25,0.5],
      ['p','C5',0.30,0.12,0.25,0.5], ['p','E5',0.45,0.20,0.25,0.55],
      ['p','G5',0.70,0.45,0.25,0.6],
      ['p','E4',0.00,0.12,0.5,0.3], ['p','E4',0.15,0.12,0.5,0.3],
      ['p','E4',0.30,0.12,0.5,0.3], ['p','G4',0.45,0.20,0.5,0.35],
      ['p','C5',0.70,0.45,0.5,0.4],
      ['t','C3',0.00,0.40,0.7], ['t','G3',0.45,0.20,0.7], ['t','C3',0.70,0.50,0.8],
      ['n',0.00,0.05,0.4], ['n',0.70,0.06,0.4],
    ],

    // 給料日:景気のいい上昇フレーズ(ドミソド↑+ベース)0.8秒
    payday: [
      ['p','C5',0.00,0.10,0.25,0.55], ['p','E5',0.12,0.10,0.25,0.55],
      ['p','G5',0.24,0.10,0.25,0.55], ['p','C6',0.36,0.35,0.25,0.6],
      ['p','G5',0.36,0.35,0.5,0.3],
      ['t','C3',0.00,0.30,0.8], ['t','C3',0.36,0.35,0.8],
      ['n',0.36,0.05,0.4],
    ],

    // 結婚:祝福っぽい和音進行(F→G→C を琴のように分散+持続和音)1.5秒
    marry: [
      ['p','F4',0.00,0.40,0.5,0.35], ['p','A4',0.07,0.38,0.5,0.35], ['p','C5',0.14,0.36,0.5,0.4],
      ['p','G4',0.50,0.40,0.5,0.35], ['p','B4',0.57,0.38,0.5,0.35], ['p','D5',0.64,0.36,0.5,0.4],
      ['p','C5',1.00,0.50,0.25,0.45], ['p','E5',1.07,0.43,0.25,0.45], ['p','G5',1.14,0.36,0.25,0.5],
      ['t','F2',0.00,0.45,0.8], ['t','G2',0.50,0.45,0.8], ['t','C3',1.00,0.50,0.85],
    ],

    // 出産:かわいい高音フレーズ(高音の跳ねるモチーフ)0.8秒
    baby: [
      ['p','E6',0.00,0.09,0.25,0.4], ['p','G6',0.11,0.09,0.25,0.4],
      ['p','E6',0.22,0.09,0.25,0.4], ['p','A6',0.33,0.14,0.25,0.45],
      ['p','G6',0.50,0.25,0.25,0.45],
      ['p','C5',0.00,0.20,0.5,0.2], ['p','C5',0.33,0.20,0.5,0.2],
      ['t','C4',0.00,0.25,0.5], ['t','G3',0.33,0.20,0.5], ['t','C4',0.50,0.28,0.5],
    ],

    // 家購入:どっしり達成感(低めのユニゾン→大きな和音)1秒
    house: [
      ['p','C4',0.00,0.16,0.5,0.45], ['p','C4',0.20,0.16,0.5,0.45],
      ['p','G4',0.40,0.20,0.5,0.5],
      ['p','C5',0.65,0.35,0.25,0.5], ['p','E5',0.65,0.35,0.25,0.4], ['p','G4',0.65,0.35,0.5,0.35],
      ['t','C2',0.00,0.38,0.9], ['t','G2',0.40,0.22,0.9], ['t','C2',0.65,0.38,0.95],
      ['n',0.00,0.06,0.5], ['n',0.40,0.05,0.4], ['n',0.65,0.08,0.5],
    ],

    // 事故:不協和音(増4度)で急降下+ノイズクラッシュ 0.8秒
    accident: [
      ['p','B4',0.00,0.18,0.5,0.5], ['p','F5',0.00,0.18,0.5,0.5],
      ['p','Bb4',0.20,0.18,0.5,0.5], ['p','E5',0.20,0.18,0.5,0.5],
      ['p','A4',0.40,0.35,0.5,0.5], ['p','Eb5',0.40,0.35,0.5,0.5],
      ['t','C2',0.40,0.38,0.9],
      ['n',0.00,0.15,0.6], ['n',0.40,0.30,0.5],
    ],

    // 火事:不安な半音下降(2声が半音でぶつかりながら下がる)1秒
    fire: [
      ['p','E5',0.00,0.20,0.5,0.45], ['p','Eb5',0.22,0.20,0.5,0.45],
      ['p','D5',0.44,0.20,0.5,0.45], ['p','C#5',0.66,0.30,0.5,0.45],
      ['p','Bb4',0.00,0.20,0.5,0.35], ['p','A4',0.22,0.20,0.5,0.35],
      ['p','Ab4',0.44,0.20,0.5,0.35], ['p','G4',0.66,0.30,0.5,0.35],
      ['t','C2',0.00,0.45,0.8], ['t','B1',0.44,0.50,0.8],
      ['n',0.05,0.10,0.25], ['n',0.35,0.10,0.25], ['n',0.66,0.12,0.3],
    ],

    // 保険で助かった:ホッとする2和音(緊張G7→安心C)0.8秒
    saved: [
      ['p','F5',0.00,0.28,0.5,0.4], ['p','B4',0.00,0.28,0.5,0.35], ['p','D5',0.00,0.28,0.5,0.35],
      ['p','E5',0.35,0.42,0.25,0.5], ['p','C5',0.35,0.42,0.5,0.4], ['p','G4',0.35,0.42,0.5,0.3],
      ['t','G2',0.00,0.30,0.8], ['t','C3',0.35,0.42,0.85],
    ],

    // 就職:決意の行進曲風(付点リズムのユニゾン+スネア風ノイズ)1秒
    job: [
      ['p','G4',0.00,0.10,0.5,0.5], ['p','G4',0.14,0.06,0.5,0.45],
      ['p','G4',0.22,0.14,0.5,0.5], ['p','C5',0.40,0.14,0.5,0.5],
      ['p','D5',0.58,0.14,0.5,0.5], ['p','G5',0.76,0.24,0.25,0.55],
      ['t','G2',0.00,0.18,0.85], ['t','G2',0.22,0.15,0.85],
      ['t','C3',0.40,0.15,0.85], ['t','D3',0.58,0.15,0.85], ['t','G2',0.76,0.24,0.9],
      ['n',0.00,0.04,0.5], ['n',0.22,0.04,0.4], ['n',0.40,0.04,0.4],
      ['n',0.58,0.04,0.4], ['n',0.76,0.06,0.55],
    ],

    // ゴール:盛大なファンファーレ(タタタター→オクターブ跳躍で締め)1.5秒
    goal: [
      ['p','G5',0.00,0.09,0.25,0.55], ['p','G5',0.11,0.09,0.25,0.55],
      ['p','G5',0.22,0.09,0.25,0.55], ['p','G5',0.33,0.25,0.25,0.6],
      ['p','E5',0.62,0.16,0.25,0.55], ['p','F5',0.80,0.16,0.25,0.55],
      ['p','G5',0.98,0.16,0.25,0.6],  ['p','C6',1.16,0.34,0.25,0.65],
      ['p','C5',0.00,0.30,0.5,0.3],   ['p','C5',0.33,0.25,0.5,0.3],
      ['p','G4',0.62,0.16,0.5,0.3],   ['p','A4',0.80,0.16,0.5,0.3],
      ['p','B4',0.98,0.16,0.5,0.3],   ['p','E5',1.16,0.34,0.5,0.4],
      ['t','C3',0.00,0.30,0.8], ['t','C3',0.33,0.25,0.8],
      ['t','G2',0.62,0.32,0.8], ['t','G2',0.98,0.16,0.8], ['t','C3',1.16,0.34,0.9],
      ['n',0.00,0.05,0.5], ['n',0.33,0.05,0.5], ['n',1.16,0.10,0.6],
    ],

    // ギャンブル勝ち:派手な上昇アルペジオ(2オクターブ駆け上がり)1秒
    win: [
      ['p','C5',0.00,0.08,0.25,0.5], ['p','E5',0.09,0.08,0.25,0.5],
      ['p','G5',0.18,0.08,0.25,0.5], ['p','C6',0.27,0.08,0.25,0.55],
      ['p','E6',0.36,0.08,0.25,0.55],['p','G6',0.45,0.08,0.25,0.55],
      ['p','C7',0.54,0.20,0.25,0.6],
      ['p','E6',0.78,0.08,0.25,0.5], ['p','C7',0.88,0.12,0.25,0.6],
      ['t','C3',0.00,0.25,0.8], ['t','G3',0.27,0.25,0.8], ['t','C4',0.54,0.44,0.85],
      ['n',0.54,0.06,0.5], ['n',0.88,0.06,0.5],
    ],

    // ギャンブル負け:しょんぼり下降(半音を含む下降+低い三角波)0.8秒
    lose: [
      ['p','E5',0.00,0.14,0.5,0.45], ['p','D5',0.16,0.14,0.5,0.45],
      ['p','C5',0.32,0.14,0.5,0.45], ['p','B4',0.48,0.30,0.5,0.45],
      ['p','G#4',0.48,0.30,0.5,0.3],
      ['t','C3',0.00,0.30,0.7], ['t','E2',0.48,0.30,0.8],
    ],

    // ハプニング:「なになに?」の2音(4度上昇を2回、語尾上がり)0.5秒
    happen: [
      ['p','A4',0.00,0.10,0.25,0.5], ['p','D5',0.12,0.14,0.25,0.55],
      ['p','A4',0.28,0.08,0.25,0.45],['p','E5',0.38,0.12,0.25,0.55],
      ['t','D3',0.00,0.20,0.6], ['t','A2',0.28,0.22,0.6],
    ],
  };

  // ジングル 1 個を再生(ノートデータ配列 → ノード生成)
  function playJingle(data) {
    stopJingle();
    const track = jingleNodes;
    for (const n of data) {
      if (n[0] === 'p')      pulse(nf(n[1]), n[2], n[3], n[4], n[5], track);
      else if (n[0] === 't') tri(nf(n[1]), n[2], n[3], n[4], track);
      else if (n[0] === 'n') noise(n[1], n[2], n[3], track);
    }
  }

  /* ---------- 公開 API ---------- */

  return {
    muted: false,

    // 初回ユーザー操作時に呼ぶ。2回目以降は resume のみ
    init() {
      try {
        if (ctx) { wake(); return; }
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return; // 非対応環境では何もしない
        ctx = new AC();
        master = ctx.createGain();
        master.gain.value = MASTER_VOL;
        master.connect(ctx.destination);
        wake();
      } catch (e) { /* 失敗しても外へ漏らさない */ }
    },

    // ミュート切替
    setMuted(b) {
      try {
        this.muted = !!b;
        if (master) master.gain.value = this.muted ? 0 : MASTER_VOL;
        if (this.muted) stopJingle();
      } catch (e) { /* 無視 */ }
    },

    // 短い効果音
    sfx(name) {
      try {
        if (!ready()) return;
        wake();
        const fn = SFX[name];
        if (fn) fn();
      } catch (e) { /* 無視 */ }
    },

    // 短いメロディ(前のジングルは止める)
    jingle(name) {
      try {
        if (!ready()) return;
        wake();
        const data = JINGLES[name];
        if (data) playJingle(data);
      } catch (e) { /* 無視 */ }
    },
  };
})();
