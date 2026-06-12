/* =========================================================
 * ときめきモドキ キャラ立ち絵(インラインSVG)
 * portraitSVG(charId, expr, size) → SVG文字列
 * expr: normal / happy / blush / serious / shock
 * =======================================================*/

const Portraits = (function () {
  const SKIN = "#ffe3d0";
  const SKIN_SHADE = "#f3c9ae";

  /* ---- 表情パーツ(女子共通) ---- */

  function eyesF(expr, iris) {
    const hl = `fill="white" opacity="0.9"`;
    switch (expr) {
      case "happy": // にっこり閉じ目
        return `
          <path d="M40 73 Q46 67 52 73" stroke="#5a3a2a" stroke-width="2.5" fill="none" stroke-linecap="round"/>
          <path d="M68 73 Q74 67 80 73" stroke="#5a3a2a" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;
      case "shock": // 白目+点目
        return `
          <ellipse cx="46" cy="73" rx="6.5" ry="8" fill="white" stroke="#5a3a2a" stroke-width="1.5"/>
          <ellipse cx="74" cy="73" rx="6.5" ry="8" fill="white" stroke="#5a3a2a" stroke-width="1.5"/>
          <circle cx="46" cy="74" r="1.8" fill="#333"/>
          <circle cx="74" cy="74" r="1.8" fill="#333"/>`;
      case "serious": // 半目
        return `
          <path d="M39 70 H53 V75 Q46 79 39 75 Z" fill="${iris}"/>
          <path d="M67 70 H81 V75 Q74 79 67 75 Z" fill="${iris}"/>
          <rect x="39" y="68" width="14" height="3" fill="#5a3a2a" rx="1.5"/>
          <rect x="67" y="68" width="14" height="3" fill="#5a3a2a" rx="1.5"/>`;
      default: { // normal / blush:ぱっちり目
        const eye = (cx) => `
          <ellipse cx="${cx}" cy="73" rx="6.5" ry="8.5" fill="${iris}"/>
          <ellipse cx="${cx}" cy="76" rx="6.5" ry="5.5" fill="#3a2a3a" opacity="0.35"/>
          <circle cx="${cx - 2.2}" cy="70" r="2.4" ${hl}/>
          <circle cx="${cx + 2.5}" cy="76" r="1.2" ${hl}/>
          <path d="M${cx - 7.5} 66 Q${cx} 61 ${cx + 7.5} 66" stroke="#5a3a2a" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;
        return eye(46) + eye(74);
      }
    }
  }

  function browsF(expr) {
    if (expr === "shock")
      return `
        <path d="M39 60 Q46 56 53 60" stroke="#5a3a2a" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M67 60 Q74 56 81 60" stroke="#5a3a2a" stroke-width="2" fill="none" stroke-linecap="round"/>`;
    if (expr === "serious")
      return `
        <path d="M39 62 L53 64" stroke="#5a3a2a" stroke-width="2" stroke-linecap="round"/>
        <path d="M81 62 L67 64" stroke="#5a3a2a" stroke-width="2" stroke-linecap="round"/>`;
    return `
      <path d="M39 63 Q46 60 53 63" stroke="#5a3a2a" stroke-width="2" fill="none" stroke-linecap="round"/>
      <path d="M67 63 Q74 60 81 63" stroke="#5a3a2a" stroke-width="2" fill="none" stroke-linecap="round"/>`;
  }

  function mouth(expr) {
    switch (expr) {
      case "happy":
        return `<path d="M54 88 Q60 94 66 88" stroke="#c75a5a" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;
      case "blush":
        return `<path d="M54 87 Q60 95 66 87 Z" fill="#e07a7a"/>`;
      case "shock":
        return `<ellipse cx="60" cy="90" rx="4" ry="5.5" fill="#a04545"/>`;
      case "serious":
        return `<path d="M55 90 H65" stroke="#c75a5a" stroke-width="2.5" stroke-linecap="round"/>`;
      default:
        return `<path d="M55 89 Q60 92 65 89" stroke="#c75a5a" stroke-width="2.2" fill="none" stroke-linecap="round"/>`;
    }
  }

  function blushMarks(expr) {
    if (expr === "blush")
      return `
        <ellipse cx="38" cy="83" rx="6" ry="3.5" fill="#ff9aa8" opacity="0.7"/>
        <ellipse cx="82" cy="83" rx="6" ry="3.5" fill="#ff9aa8" opacity="0.7"/>
        <path d="M34 81 L36 85 M38 80 L40 84 M42 81 L44 85" stroke="#e87a8a" stroke-width="1" opacity="0.8"/>
        <path d="M78 81 L80 85 M82 80 L84 84 M86 81 L88 85" stroke="#e87a8a" stroke-width="1" opacity="0.8"/>`;
    if (expr === "happy")
      return `
        <ellipse cx="38" cy="83" rx="5" ry="3" fill="#ffb3bd" opacity="0.55"/>
        <ellipse cx="82" cy="83" rx="5" ry="3" fill="#ffb3bd" opacity="0.55"/>`;
    return "";
  }

  /* ---- 顔ベース(女子) ---- */

  function faceF() {
    return `
      <path d="M34 92 Q33 84 33 76 L87 76 Q87 84 86 92 Z" fill="${SKIN}" opacity="0"/>
      <ellipse cx="32" cy="74" rx="4" ry="6" fill="${SKIN}"/>
      <ellipse cx="88" cy="74" rx="4" ry="6" fill="${SKIN}"/>
      <path d="M33 62 Q33 44 60 44 Q87 44 87 62 Q87 80 78 90 Q69 99 60 99 Q51 99 42 90 Q33 80 33 62 Z" fill="${SKIN}"/>
      <path d="M54 104 Q60 106 66 104 L66 94 H54 Z" fill="${SKIN}"/>
      <path d="M54 96 Q60 101 66 96 L66 94 H54 Z" fill="${SKIN_SHADE}"/>`;
  }

  /* ---- セーラー服 ---- */

  function sailor(ribbonColor) {
    return `
      <path d="M28 140 Q28 116 45 109 L60 104 L75 109 Q92 116 92 140 Z" fill="#3a4a7a"/>
      <path d="M48 107 L60 104 L72 107 L60 122 Z" fill="white"/>
      <path d="M46 108 L60 124 L74 108 L78 112 L60 132 L42 112 Z" fill="#2d3a62"/>
      <path d="M44 110 L60 127 L76 110" stroke="white" stroke-width="1.5" fill="none"/>
      <path d="M60 122 L66 128 L60 138 L54 128 Z" fill="${ribbonColor}"/>
      <path d="M53 124 Q49 120 52 117 L60 122 L68 117 Q71 120 67 124 L60 128 Z" fill="${ribbonColor}"/>`;
  }

  /* ============ しおり(図書委員・爆弾処理が趣味) ============ */

  function shiori(expr) {
    const HAIR = "#6a5494";
    const HAIR_SH = "#584683";
    return `
      <!-- 後ろ髪:ボブ -->
      <path d="M27 64 Q26 38 60 36 Q94 38 93 64 Q94 88 88 100 Q86 106 80 104 L78 88 L42 88 L40 104 Q34 106 32 100 Q26 88 27 64 Z" fill="${HAIR_SH}"/>
      ${faceF()}
      ${sailor("#7a5cc5")}
      <!-- 前髪:ぱっつん -->
      <path d="M31 66 Q29 40 60 38 Q91 40 89 66 L84 60 Q82 52 78 58 L74 52 Q70 46 66 54 L62 48 Q60 45 58 48 L54 54 Q50 46 46 52 L42 58 Q38 52 36 60 Z" fill="${HAIR}"/>
      <!-- 赤と青のヘアピン(どっちを切る?) -->
      <rect x="36" y="56" width="12" height="2.6" rx="1.3" fill="#e23b3b" transform="rotate(18 36 56)"/>
      <rect x="35" y="61" width="12" height="2.6" rx="1.3" fill="#3b6ae2" transform="rotate(18 35 61)"/>
      ${browsF(expr)}
      ${eyesF(expr, "#7a5cc5")}
      ${blushMarks(expr)}
      ${mouth(expr)}
      <!-- 眼鏡 -->
      <g stroke="#4a3a6a" stroke-width="1.8" fill="rgba(255,255,255,0.14)">
        <rect x="37" y="65" width="18" height="15" rx="6"/>
        <rect x="65" y="65" width="18" height="15" rx="6"/>
        <path d="M55 71 Q60 68 65 71" fill="none"/>
      </g>
      <!-- 胸元に小さな爆弾ブローチ -->
      <circle cx="60" cy="133" r="4" fill="#333"/>
      <path d="M60 129 Q62 126 64 127" stroke="#333" stroke-width="1.4" fill="none"/>
      <circle cx="64.5" cy="126.5" r="1.2" fill="#ffb03b"/>`;
  }

  /* ============ ひかり(転校生・自称17歳) ============ */

  function hikari(expr) {
    const HAIR = "#ffb0c8";
    const HAIR_SH = "#f095b4";
    return `
      <!-- ツインテール -->
      <path d="M30 60 Q18 62 16 84 Q14 104 22 118 Q26 122 28 116 Q24 100 28 84 Q30 70 34 64 Z" fill="${HAIR_SH}"/>
      <path d="M90 60 Q102 62 104 84 Q106 104 98 118 Q94 122 92 116 Q96 100 92 84 Q90 70 86 64 Z" fill="${HAIR_SH}"/>
      <path d="M28 66 Q26 38 60 36 Q94 38 92 66 Q92 76 88 80 L84 66 L36 66 L32 80 Q28 76 28 66 Z" fill="${HAIR_SH}"/>
      ${faceF()}
      ${sailor("#ff6fa5")}
      <!-- 前髪:80年代風ふんわり -->
      <path d="M30 64 Q28 38 60 36 Q92 38 90 64 Q86 68 84 62 Q84 50 76 56 Q68 60 64 50 Q60 44 56 50 Q52 60 44 56 Q36 50 36 62 Q34 68 30 64 Z" fill="${HAIR}"/>
      <!-- 星のヘアクリップ -->
      <path d="M44 50 L46 55 L51 55 L47 58 L49 63 L44 60 L39 63 L41 58 L37 55 L42 55 Z" fill="#ffd23b" stroke="#e8a800" stroke-width="0.8"/>
      ${browsF(expr)}
      ${eyesF(expr, "#e8657f")}
      <!-- 年輪を感じさせる輝きの追加ハイライト -->
      ${expr === "normal" || expr === "blush" ? `<path d="M42 78 L43.5 81 L46.5 81.7 L43.5 82.4 L42 85 L40.5 82.4 L37.5 81.7 L40.5 81 Z" fill="white" opacity="0.95"/>` : ""}
      ${blushMarks(expr)}
      ${mouth(expr)}`;
  }

  /* ============ 番長(敬語しか話せない) ============ */

  function bancho(expr) {
    const HAIR = "#2a2a33";
    const eyes =
      expr === "happy"
        ? `<path d="M42 74 Q47 70 52 74" stroke="#222" stroke-width="2.5" fill="none" stroke-linecap="round"/>
           <path d="M68 74 Q73 70 78 74" stroke="#222" stroke-width="2.5" fill="none" stroke-linecap="round"/>`
        : expr === "shock"
        ? `<circle cx="47" cy="74" r="2.2" fill="#222"/><circle cx="73" cy="74" r="2.2" fill="#222"/>
           <circle cx="47" cy="74" r="6" fill="none" stroke="#222" stroke-width="1.2"/>
           <circle cx="73" cy="74" r="6" fill="none" stroke="#222" stroke-width="1.2"/>`
        : `<path d="M42 72 H52 V76 H42 Z" rx="2" fill="#222"/>
           <path d="M68 72 H78 V76 H68 Z" rx="2" fill="#222"/>`;
    const brows =
      expr === "shock"
        ? `<path d="M40 62 Q47 58 54 62" stroke="#222" stroke-width="3.5" fill="none" stroke-linecap="round"/>
           <path d="M66 62 Q73 58 80 62" stroke="#222" stroke-width="3.5" fill="none" stroke-linecap="round"/>`
        : `<path d="M40 64 L54 61" stroke="#222" stroke-width="3.5" stroke-linecap="round"/>
           <path d="M80 64 L66 61" stroke="#222" stroke-width="3.5" stroke-linecap="round"/>`;
    const mouthB =
      expr === "happy" || expr === "blush"
        ? `<path d="M52 90 Q60 96 68 90" stroke="#8a4a3a" stroke-width="2.5" fill="none" stroke-linecap="round"/>`
        : expr === "shock"
        ? `<ellipse cx="60" cy="91" rx="5" ry="6" fill="#7a3a2a"/>`
        : `<path d="M52 91 H68" stroke="#8a4a3a" stroke-width="2.5" stroke-linecap="round"/>`;
    return `
      <!-- 学ラン(肩幅広め) -->
      <path d="M22 140 Q22 112 44 106 L60 102 L76 106 Q98 112 98 140 Z" fill="#1d1d26"/>
      <path d="M52 106 L60 102 L68 106 L64 118 H56 Z" fill="white"/>
      <path d="M50 104 L60 118 L70 104 L74 108 L60 130 L46 108 Z" fill="#15151c"/>
      <circle cx="60" cy="124" r="2" fill="#d4af37"/>
      <circle cx="60" cy="133" r="2" fill="#d4af37"/>
      <!-- 立ち襟 -->
      <path d="M44 106 L52 100 L54 110 L46 112 Z" fill="#2d2d3a"/>
      <path d="M76 106 L68 100 L66 110 L74 112 Z" fill="#2d2d3a"/>
      <!-- 顔(やや角ばり) -->
      <ellipse cx="31" cy="74" rx="4" ry="6" fill="${SKIN}"/>
      <ellipse cx="89" cy="74" rx="4" ry="6" fill="${SKIN}"/>
      <path d="M32 60 Q32 44 60 44 Q88 44 88 60 L88 78 Q88 90 78 96 Q69 101 60 101 Q51 101 42 96 Q32 90 32 78 Z" fill="${SKIN}"/>
      <path d="M53 106 Q60 108 67 106 L67 95 H53 Z" fill="${SKIN}"/>
      <path d="M53 97 Q60 102 67 97 L67 95 H53 Z" fill="${SKIN_SHADE}"/>
      <!-- リーゼント -->
      <path d="M30 62 Q28 40 54 38 Q84 34 96 46 Q104 54 96 58 Q90 60 84 56 Q88 64 80 64 Q74 64 72 58 Q70 52 60 52 Q44 52 38 58 Q34 62 30 62 Z" fill="${HAIR}"/>
      <path d="M58 40 Q80 38 92 47" stroke="#4a4a5a" stroke-width="2" fill="none" opacity="0.8"/>
      <!-- 頬の傷 -->
      <path d="M78 82 L84 88 M80 88 L84 84" stroke="#c98a7a" stroke-width="1.5" stroke-linecap="round"/>
      ${brows}
      ${eyes}
      ${expr === "blush" ? `<ellipse cx="40" cy="84" rx="6" ry="3.5" fill="#ff9aa8" opacity="0.6"/><ellipse cx="80" cy="84" rx="6" ry="3.5" fill="#ff9aa8" opacity="0.6"/>` : ""}
      ${mouthB}`;
  }

  const DRAW = { shiori, bancho, hikari };

  function svg(charId, expr = "normal", size = 96) {
    const body = DRAW[charId] ? DRAW[charId](expr) : "";
    return (
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 140" width="${size}" height="${Math.round(size * 140 / 120)}">` +
      body +
      `</svg>`
    );
  }

  return { svg };
})();
