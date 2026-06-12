/* =========================================================
 * モドキクエストII データ定義
 * マップ・モンスター・呪文・アイテム・イベント
 * =======================================================*/

/* ---------- 呪文 ---------- */

const SPELLS = {
  cure:   { name: "キュア",   mp: 3, type: "heal",  power: [30, 42], field: true },
  curera: { name: "キュアラ", mp: 8, type: "heal",  power: [80, 105], field: true },
  spark:  { name: "スパーク", mp: 2, type: "dmg",   power: [10, 20] },
  bachi:  { name: "バチバチ", mp: 5, type: "dmgAll", power: [12, 22] },
  sparga: { name: "スパーガ", mp: 8, type: "dmg",   power: [55, 78] },
  nemure: { name: "ねむれ",   mp: 3, type: "sleep" },
  modori: { name: "モドリ",   mp: 4, type: "warp",  fieldOnly: true, field: true },
};

/* ---------- キャラクター ---------- */

const PARTY_DEFS = {
  ganba: {
    name: "ガンバ", title: "ガンバリアの王子",
    growth: { hp: [18, 10], mp: [0, 0], atk: [6, 4], def: [5, 3], agi: [3, 2] },
    spellsAt: {},
  },
  nonbi: {
    name: "ノンビ", title: "ノンビリアの王子",
    growth: { hp: [16, 8], mp: [6, 4], atk: [4, 3], def: [4, 2.4], agi: [4, 2.5] },
    spellsAt: { 1: ["cure"], 4: ["spark"], 7: ["nemure"], 10: ["curera"] },
  },
  myako: {
    name: "ミャーコ", title: "ミャウブルクの王女",
    growth: { hp: [12, 6.5], mp: [10, 6], atk: [3, 1.8], def: [3, 2], agi: [6, 3] },
    spellsAt: { 1: ["spark", "bachi", "modori"], 9: ["sparga"], 12: ["curera"] },
  },
};

/* レベルアップに必要な累計EXP(QoL: ゆるやかな曲線) */
function expForLevel(lv) {
  let total = 0;
  for (let k = 1; k < lv; k++) total += 5 * k * k;
  return total;
}

/* ---------- アイテム・装備 ---------- */

const ITEMS = {
  herb:  { name: "げんきそう",   type: "heal", power: [38, 48], price: 8 },
  wing:  { name: "ハトのつばさ", type: "warp", price: 15 },
  bakeneko: { name: "ばけねこ草", type: "key" },
};

const EQUIP = {
  bat:    { name: "ヒノキバット",   slot: "weapon", atk: 3,  price: 15,  who: ["ganba", "nonbi"] },
  bronze: { name: "ブロンズソード", slot: "weapon", atk: 8,  price: 110, who: ["ganba", "nonbi"] },
  iron:   { name: "アイアンソード", slot: "weapon", atk: 16, price: 450, who: ["ganba", "nonbi"] },
  herosw: { name: "ヒーローソード", slot: "weapon", atk: 26, price: 9999, who: ["ganba"] },
  jarashi:{ name: "ネコジャラシ",   slot: "weapon", atk: 6,  price: 80,  who: ["myako"] },
  rod:    { name: "マジカルロッド", slot: "weapon", atk: 12, price: 500, who: ["myako", "nonbi"] },
  shirt:  { name: "ぬのシャツ",     slot: "armor",  def: 2,  price: 10,  who: ["ganba", "nonbi", "myako"] },
  leather:{ name: "レザーベスト",   slot: "armor",  def: 6,  price: 70,  who: ["ganba", "nonbi", "myako"] },
  chain:  { name: "チェインメイル", slot: "armor",  def: 11, price: 300, who: ["ganba", "nonbi"] },
  plate:  { name: "プレートアーマー", slot: "armor", def: 18, price: 9999, who: ["ganba"] },
  woodsh: { name: "ウッドガード",   slot: "shield", def: 3,  price: 40,  who: ["ganba", "nonbi"] },
  ironsh: { name: "アイアンガード", slot: "shield", def: 8,  price: 180, who: ["ganba", "nonbi"] },
};

const SHOPS = {
  rirefu:  { name: "リレフのみせ",   items: ["bat", "shirt", "woodsh"], goods: ["herb", "wing"] },
  nonbiria:{ name: "ノンビリアのみせ", items: ["bronze", "leather", "woodsh"], goods: ["herb", "wing"] },
  oar:     { name: "オールのみせ",   items: ["iron", "chain", "ironsh", "jarashi", "rod"], goods: ["herb", "wing"] },
};

/* ---------- モンスター ---------- */

const MONSTERS = {
  purupuru: { name: "ぷるぷる", art: "slime", pal: ["#3b7ae2", "#7db0ff", "#16306b"], hp: 7, atk: 8, def: 2, agi: 3, exp: 2, gold: 4, acts: ["attack"] },
  piyodori: { name: "ぴよどり", art: "bird", pal: ["#f0c43b", "#ffe78a", "#8a6a14"], hp: 9, atk: 10, def: 3, agi: 8, exp: 3, gold: 5, acts: ["attack"] },
  kinoko:   { name: "きのこぼうや", art: "mush", pal: ["#e25b5b", "#ffd9d9", "#6b1616"], hp: 13, atk: 12, def: 4, agi: 4, exp: 5, gold: 7, acts: ["attack", "attack", "sleep"] },
  honehone: { name: "ホネホネ", art: "skel", pal: ["#e8e3d8", "#b5ab97", "#3a3a3a"], hp: 22, atk: 17, def: 8, agi: 8, exp: 10, gold: 12, acts: ["attack"] },
  robe:     { name: "ローブのなにか", art: "mage", pal: ["#6a4a9c", "#9b7ad4", "#241638"], hp: 18, atk: 12, def: 6, agi: 9, exp: 12, gold: 14, acts: ["attack", "spark"] },
  kara:     { name: "カラのよろい", art: "armor", pal: ["#8a95a8", "#c5cede", "#3a4252"], hp: 34, atk: 20, def: 16, agi: 4, exp: 18, gold: 20, acts: ["attack"] },
  yorudori: { name: "ヨルどり", art: "bird", pal: ["#5a4a8a", "#8a78c2", "#241a44"], hp: 24, atk: 22, def: 8, agi: 16, exp: 16, gold: 15, acts: ["attack"] },
  buriki:   { name: "ブリキマン", art: "robot", pal: ["#b8b29a", "#e5e0cb", "#55503c"], hp: 30, atk: 30, def: 22, agi: 10, exp: 26, gold: 28, acts: ["attack"] },
  chibidra: { name: "チビドラゴン", art: "dragon", pal: ["#4aa85a", "#8ad494", "#1c4a24"], hp: 44, atk: 26, def: 12, agi: 10, exp: 30, gold: 30, acts: ["attack", "attack", "breath"] },
  ginpuru:  { name: "ぎんぷる", art: "slime", pal: ["#c5cede", "#f2f5fa", "#5a6478"], hp: 5, atk: 12, def: 60, agi: 40, exp: 120, gold: 15, acts: ["attack"], flees: true },
  honeknight: { name: "ホネホネナイト", art: "skel", pal: ["#d8c5a0", "#a89070", "#3a2a1a"], hp: 40, atk: 26, def: 14, agi: 10, exp: 40, gold: 40, acts: ["attack"] },
  dekadra:  { name: "デカドラゴン", art: "dragon", pal: ["#c2543b", "#e89a78", "#5a1f10"], hp: 60, atk: 34, def: 16, agi: 12, exp: 48, gold: 45, acts: ["attack", "breath"] },
  kuroyoroi:{ name: "クロのよろい", art: "armor", pal: ["#3a3a44", "#6a6a7c", "#15151c"], hp: 55, atk: 34, def: 24, agi: 8, exp: 45, gold: 40, acts: ["attack"] },
  yabairobe:{ name: "ローブのやばいの", art: "mage", pal: ["#9c2a2a", "#d46a6a", "#380f0f"], hp: 40, atk: 26, def: 12, agi: 14, exp: 42, gold: 38, acts: ["attack", "spark", "sleep", "heal"] },
  /* ボス(2回行動) */
  tekkamen: { name: "テッカメン", art: "armor", pal: ["#4a7a9c", "#8ab8d4", "#1c3344"], hp: 230, atk: 56, def: 24, agi: 10, exp: 200, gold: 300, acts: ["attack", "attack", "breath"], boss: true, twice: true, scale: 5 },
  zannen:   { name: "じゃしんかんザンネン", art: "mage", pal: ["#2a2a3a", "#8a5cf5", "#0c0c14"], hp: 380, atk: 72, def: 20, agi: 14, exp: 500, gold: 0, acts: ["attack", "sparkPlus", "sleep", "heal"], boss: true, twice: true, scale: 5 },
  gudaguda: { name: "はかいしんグダグダ", art: "dragon", pal: ["#7a3a9c", "#b87ad4", "#2c1238"], hp: 450, atk: 85, def: 22, agi: 12, exp: 0, gold: 0, acts: ["attack", "breath"], boss: true, twice: true, scale: 6 },
};

/* 出現テーブル(ゾーンごとのグループ候補) */
const ENCOUNTERS = {
  field1: [
    ["purupuru", 1, 3], ["piyodori", 1, 2], ["kinoko", 1, 2],
    ["purupuru", 1, 2, "piyodori", 1, 1],
  ],
  cave: [
    ["honehone", 1, 2], ["robe", 1, 2], ["kara", 1, 1],
    ["honehone", 1, 1, "robe", 1, 1],
  ],
  field2: [
    ["chibidra", 1, 1], ["buriki", 1, 2], ["yorudori", 2, 3],
    ["ginpuru", 1, 1], ["buriki", 1, 1, "yorudori", 1, 2],
  ],
  tower: [
    ["kara", 1, 2], ["chibidra", 1, 2], ["buriki", 1, 2], ["yabairobe", 1, 1],
  ],
  final: [
    ["kuroyoroi", 1, 2], ["yabairobe", 1, 2], ["dekadra", 1, 1],
    ["kuroyoroi", 1, 1, "yabairobe", 1, 1], ["ginpuru", 1, 2],
  ],
};

const ENCOUNTER_RATE = { field1: 0.10, cave: 0.13, field2: 0.11, tower: 0.13, final: 0.13 };

/* =========================================================
 * マップ
 *  w=海 g=草 f=森 m=山 s=砂 #=壁 .=床 r=カーペット
 *  <=出口 >=下り階段 ^=上り階段
 *  A〜I = ワールド上の施設入口
 * =======================================================*/

const WORLD_ROWS = [
  "wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww", // 0
  "wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww", // 1
  "wwgggggggggggggggwwwwwwwwwwwwwwwwwwwwwww", // 2
  "wwgfffggggggggggggwwwwwwwwwwwwwwwwwwwwww", // 3
  "wwgfffggmmggggggggwwwwwwmmmmmmmmmmmmmwww", // 4
  "wwggggggmmmgggggggwwwwwwmggggggggggggwww", // 5
  "wwggggggAgmmggggggwwwwwwmggffggggfggmwww", // 6
  "wwgggggggggmmgffggwwwwwwggGggggggggggwww", // 7
  "wwggggggggggmmgggggwwwwwgggggggggggggwww", // 8
  "wwgggggggggmmmmFmggwwwwwgffggggggggggwww", // 9
  "wwgggffggggggmmmmmggwwwwgffggggmmggggwww", // 10
  "wwggfffggggggggmmmgggwwwgggggmmgggggwwww", // 11
  "wwgggBgggggggggggggggwwwgggggmmgggHggwww", // 12
  "wwgggggggggggggggggwwwwwgggggggggggggwww", // 13
  "wwggggggggffggggggwwwwwwgggffggggggggwww", // 14
  "wwgggggggffgggggggwwwwwwgggggggggggggwww", // 15
  "wwgggggggggggCgggggwwwwwssssssssssssswww", // 16
  "wwgggggggggggggggggwwwwwwwwwwwwwwwwwwwww", // 17
  "wwggggggggggggggggEwwwwwwwwwwwwwwwwwwwww", // 18
  "wwgggggggggggggggggwwwwwwwwwwwwwwwwwwwww", // 19
  "wwggffgggggggggggggwwwwwwwmmmmmmmmmwwwww", // 20
  "wwggDggggggggggggggwwwwwwwmgggggggmwwwww", // 21
  "wwgggggggggggggggwwwwwwwwwmgggIgggmwwwww", // 22
  "wwgggggggggggggwwwwwwwwwwwmgggggggmwwwww", // 23
  "wwwwwwwwwwwwwwwwwwwwwwwwwwmmggggmmmwwwww", // 24
  "wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww", // 25
  "wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww", // 26
  "wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww", // 27
];

const MAPS = {
  world: {
    name: "せかい",
    rows: WORLD_ROWS,
    outdoor: true,
    zone: (x, y) => (x <= 21 ? "field1" : "field2"),
    links: {
      A: { map: "castle1", x: 6, y: 6 },
      B: { map: "village", x: 6, y: 6 },
      C: { map: "castle2", x: 6, y: 6 },
      D: { map: "ruins", x: 6, y: 6 },
      E: { map: "port", x: 6, y: 6 },
      F: { map: "cave", x: 7, y: 9 },
      G: { map: "tower", x: 7, y: 9 },
      H: { map: "shrine", x: 4, y: 4 },
      I: { map: "final1", x: 7, y: 8 },
    },
  },

  castle1: {
    name: "ガンバリアじょう",
    rows: [
      "#############",
      "#####rrr#####",
      "####rrrrr####",
      "#...rrrrr...#",
      "#...........#",
      "#...........#",
      "#...........#",
      "######<######",
      "#############",
    ],
    exit: { x: 8, y: 7 },
    npcs: [
      { x: 6, y: 2, art: "king", event: "king1" },
      { x: 4, y: 4, art: "soldier", text: "へいし「ひがしの どうくつには『ゆうきのご紋章』が ねむっているそうです。ガイコツが ばんを しているとか」" },
      { x: 8, y: 4, art: "soldier", text: "へいし「みなみの ノンビリアじょうの王子も 旅に出る…と聞きましたが、あの方が朝おきられるかどうか」" },
    ],
    chests: [{ x: 2, y: 3, gold: 30, id: "c1g" }],
  },

  village: {
    name: "リレフのむら",
    rows: [
      "#############",
      "#.....#.....#",
      "#.....#.....#",
      "#...........#",
      "#.....#.....#",
      "#.....#.....#",
      "#...........#",
      "######<######",
      "#############",
    ],
    exit: { x: 5, y: 13 },
    npcs: [
      { x: 3, y: 2, art: "villager", event: "shop_rirefu" },
      { x: 9, y: 2, art: "villager", event: "inn_rirefu" },
      { x: 3, y: 5, art: "elder", text: "ろうじん「ミャウブルクの くにはほろび、王女さまは ねこに されてしまったそうじゃ。にしの はいきょに いまも…」" },
      { x: 9, y: 5, art: "villager", text: "むらびと「『ばけねこ草』をつかえば、ねこにされた人も もとに もどるらしいよ。はいきょの たからばこで 見たような」" },
    ],
    chests: [],
  },

  castle2: {
    name: "ノンビリアじょう",
    rows: [
      "#############",
      "####rrr######",
      "#...rrr.....#",
      "#...........#",
      "#..##.##....#",
      "#..#...#....#",
      "#..#...#....#",
      "######<######",
      "#############",
    ],
    exit: { x: 13, y: 17 },
    npcs: [
      { x: 5, y: 2, art: "king", event: "king2" },
      { x: 10, y: 3, art: "villager", event: "shop_nonbiria" },
      { x: 5, y: 5, art: "nonbi", event: "nonbi_join" },
      { x: 9, y: 6, art: "soldier", text: "へいし「みなみの みなとまち オールに行けば、ふねが 手に入るかもしれません」" },
    ],
    chests: [],
  },

  ruins: {
    name: "ミャウブルクのはいきょ",
    rows: [
      "#############",
      "#.#.......#.#",
      "#...##.##...#",
      "#..#..#..#..#",
      "#...........#",
      "#..#..#..#..#",
      "#.#.......#.#",
      "######<######",
      "#############",
    ],
    exit: { x: 4, y: 22 },
    npcs: [
      { x: 5, y: 4, art: "cat", event: "cat_princess" },
    ],
    chests: [{ x: 10, y: 2, item: "bakeneko", id: "ruins_bake" }],
  },

  port: {
    name: "みなとまちオール",
    rows: [
      "#############",
      "#.....#.....#",
      "#.....#.....#",
      "#...........#",
      "#..#.....#..#",
      "#...........#",
      "#...........#",
      "######<######",
      "#############",
    ],
    exit: { x: 17, y: 18 },
    npcs: [
      { x: 3, y: 2, art: "villager", event: "shop_oar" },
      { x: 9, y: 2, art: "villager", event: "inn_oar" },
      { x: 6, y: 5, art: "sailor", event: "sailor_ship" },
      { x: 10, y: 5, art: "villager", text: "まちびと「うみのむこうの とうには『ひるねのご紋章』が。きたの ほこらの仙人は 紋章あつめに くわしいぞ」" },
    ],
    chests: [],
  },

  cave: {
    name: "ガイコツのどうくつ",
    zone: () => "cave",
    dark: true,
    rows: [
      "###############",
      "#.....#.......#",
      "#.###.#.#####.#",
      "#.#...#.....#.#",
      "#.#.#######.#.#",
      "#.#.......#.#.#",
      "#.#######.#.#.#",
      "#.........#...#",
      "#.#########.###",
      "#.............#",
      "#######<#######",
    ],
    exit: { x: 15, y: 8 },
    npcs: [],
    chests: [
      { x: 4, y: 3, event: "crest_brave", id: "cave_crest" },
      { x: 13, y: 1, gold: 120, id: "cave_g" },
    ],
  },

  tower: {
    name: "ひるねのとう",
    zone: () => "tower",
    rows: [
      "###############",
      "#.............#",
      "######.#.######",
      "#......#......#",
      "#.####.#.####.#",
      "#......#......#",
      "######.#.######",
      "#......#......#",
      "#.####.#.####.#",
      "#......<......#",
      "###############",
    ],
    exit: { x: 26, y: 8 },
    npcs: [
      { x: 7, y: 1, art: "statue", event: "boss_tekkamen" },
    ],
    chests: [
      { x: 3, y: 3, event: "chest_herosw", id: "tower_sw" },
      { x: 11, y: 3, gold: 300, id: "tower_g" },
    ],
  },

  shrine: {
    name: "せんにんのほこら",
    rows: [
      "#########",
      "#.......#",
      "#.......#",
      "#.......#",
      "#.......#",
      "####<####",
      "#########",
    ],
    exit: { x: 34, y: 13 },
    npcs: [
      { x: 4, y: 2, art: "elder", event: "hermit" },
    ],
    chests: [],
  },

  final1: {
    name: "じゃしんかんのしろ",
    zone: () => "final",
    rows: [
      "###############",
      "######.>.######",
      "######...######",
      "######...######",
      "#######.#######",
      "#######.#######",
      "#######.#######",
      "#######.#######",
      "#######.#######",
      "#######<#######",
      "###############",
    ],
    exit: { x: 30, y: 23 },
    links: { ">": { map: "final2", x: 7, y: 6 } },
    npcs: [
      { x: 7, y: 5, art: "darksoldier", event: "final_gate" },
    ],
    chests: [
      { x: 6, y: 2, event: "chest_plate", id: "f1_plate" },
      { x: 8, y: 2, gold: 500, id: "f1_g" },
    ],
  },

  final2: {
    name: "じゃしんかんのまどう",
    zone: () => "final",
    rows: [
      "###############",
      "######rrr######",
      "######rrr######",
      "######rrr######",
      "#.....rrr.....#",
      "#.....rrr.....#",
      "#.....rrr.....#",
      "#######^#######",
      "###############",
    ],
    links: { "^": { map: "final1", x: 7, y: 2 } },
    npcs: [
      { x: 7, y: 2, art: "priest", event: "boss_zannen" },
    ],
    chests: [],
  },
};

/* =========================================================
 * イベント
 *  各イベントは「アクションの配列」を返す関数。
 *  アクション: {msg} {flag} {gold} {item} {heal} {join}
 *             {battle, win:[...]} {shop} {inn} {confirm, yes, no}
 *             {warp:{map,x,y}} {ending} {learnEquip}
 * =======================================================*/

const EVENTS = {
  king1(g) {
    if (g.flags.cleared) {
      return [{ msg: "王さま「えいゆうたちよ!せかいは すくわれた。ゆっくり やすむがよい」" }];
    }
    if (!g.flags.quest) {
      return [
        { msg: "王さま「よくぞ来た、わが息子ガンバよ。じゃしんかんザンネンが せかいの はかいを たくらんでおる」" },
        { msg: "王さま「3つの『ご紋章』を集め、みなみの島の ザンネンのしろへ むかうのじゃ。なかまも さがすがよい」" },
        { msg: "王さま「旅のしたくに 50ゴールドを あたえよう。…ぶっかだかで すまぬ」" },
        { gold: 50 },
        { flag: "quest" },
        { msg: "* このゲームはオートセーブです。ぜんめつしても お金は へりません。あんしんして ガンバって ください" },
      ];
    }
    return [
      { msg: "王さま「ご紋章は『ゆうき』『やさしさ』『ひるね』の3つ。あつまったら きたの ほこらの仙人を たずねよ」" },
      { heal: true },
      { msg: "* 王さまの はからいで パーティは ぜんかいふくした!" },
    ];
  },

  king2(g) {
    if (g.flags.nonbiJoined) {
      return [{ msg: "ノンビリア王「むすこを よろしくたのむ。…ちゃんと 朝 おきておるか?」" }];
    }
    return [
      { msg: "ノンビリア王「おお、ガンバ王子!うちのノンビも 旅に出る…はずなのじゃが、まだ しろの 中に おるようでな」" },
      { msg: "ノンビリア王「おくの へやで 寝ておる。たたきおこして 連れていってくれ」" },
    ];
  },

  nonbi_join(g) {
    if (g.flags.nonbiJoined) return [];
    return [
      { msg: "ノンビ「…………すぴー」" },
      { msg: "ノンビ「…はっ!? 旅に出る日!? …あと5ふん…いや、行きます。行きますとも」" },
      { msg: "* ノンビが なかまに くわわった!" },
      { join: "nonbi" },
      { flag: "nonbiJoined" },
    ];
  },

  cat_princess(g) {
    if (g.flags.myakoJoined) return [];
    if (g.items.bakeneko) {
      return [
        { msg: "ねこ「ニャー……(あ、それは…!)」" },
        { msg: "* ばけねこ草を つかった! まばゆい ひかりが ねこを つつむ…!" },
        { msg: "ミャーコ「もどった〜!わたしは ミャウブルクの王女 ミャーコ。じゃしんかんに ねこに されてたの」" },
        { msg: "ミャーコ「おれいに これを。…にくきゅうは なくなったけど、また いっしょに たたかいましょ」" },
        { msg: "* ミャーコが なかまに くわわった!" },
        { msg: "* 『やさしさのご紋章』を 手に入れた!" },
        { join: "myako" },
        { takeItem: "bakeneko" },
        { flag: "myakoJoined" },
        { flag: "crestKind" },
      ];
    }
    return [
      { msg: "ねこ「ニャー、ニャニャーン(わたしは ミャウブルクの王女です。しんじてください)」" },
      { msg: "ねこ「ニャーン…(『ばけねこ草』があれば もとに もどれるのに…この はいきょの どこかに あったはず)」" },
      { msg: "* ふしぎと いいたいことが ぜんぶ わかった" },
    ];
  },

  sailor_ship(g) {
    if (g.flags.hasShip) {
      return [{ msg: "ふなのり「ふねは そとの うみに とめてあるぜ。うみに むかって あるけば のれる!」" }];
    }
    return [
      { msg: "ふなのり「ふねが ほしい? ちょうどいい!おれのふねに まものが すみついちまって こまってたんだ」" },
      { msg: "ふなのり「たいじしてくれたら ふねは あんたに やるよ。…しょぶんに こまってたんだ、いやマジで」" },
      {
        battle: ["honehone", "honehone", "robe"],
        win: [
          { msg: "ふなのり「たすかったぜ!やくそくどおり ふねは あんたのもんだ。そとの うみに とめてある」" },
          { msg: "* ふねを 手に入れた! うみに むかって あるくと じょうせん できる" },
          { flag: "hasShip" },
        ],
      },
    ];
  },

  crest_brave(g) {
    if (g.flags.crestBrave) return [{ msg: "* たからばこは からっぽだ" }];
    return [
      { msg: "* たからばこに 手をかけた、そのとき! ガイコツの ばんにんが おそいかかってきた!" },
      {
        battle: ["honeknight", "honeknight"],
        win: [
          { msg: "* 『ゆうきのご紋章』を 手に入れた!" },
          { flag: "crestBrave" },
        ],
      },
    ];
  },

  boss_tekkamen(g) {
    if (g.flags.crestNap) return [];
    return [
      { msg: "テッカメン「ようこそ ひるねのとうへ。ここから さきは とおさん。わたしの ひるねの じゃまになるのでな」" },
      {
        battle: ["tekkamen"],
        win: [
          { msg: "テッカメン「みごとだ…。これで こころおきなく ねむれる…ぐう」" },
          { msg: "* 『ひるねのご紋章』を 手に入れた!" },
          { flag: "crestNap" },
        ],
      },
    ];
  },

  hermit(g) {
    const crests = ["crestBrave", "crestKind", "crestNap"].filter((f) => g.flags[f]).length;
    if (g.flags.hasKey) {
      return [
        { msg: "せんにん「ザンネンのしろは みなみの島じゃ。ふねで むかうがよい」" },
        { heal: true },
        { msg: "* せんにんの ちからで パーティは ぜんかいふくした!" },
      ];
    }
    if (crests >= 3) {
      return [
        { msg: "せんにん「おお…3つのご紋章が そろっておる!ゆうき、やさしさ、そして じゅうぶんな すいみん…」" },
        { msg: "せんにん「にんげんに ひつような すべてじゃ。これで ザンネンのしろの とびらが ひらく」" },
        { msg: "* 『ゆるしのカギ』を さずかった!" },
        { flag: "hasKey" },
        { heal: true },
        { msg: "* パーティは ぜんかいふくした!" },
      ];
    }
    return [
      { msg: `せんにん「ご紋章は ${crests}つ か。3つ そろえて まいるがよい。『ゆうき』は ひがしのどうくつ、『やさしさ』は ねこのおひめさま、『ひるね』は うみのむこうの とう じゃ」` },
      { heal: true },
      { msg: "* せんにんの ちからで パーティは ぜんかいふくした!" },
    ];
  },

  final_gate(g) {
    if (g.flags.gateOpen) return [];
    if (g.flags.hasKey) {
      return [
        { msg: "やみのへいし「む…『ゆるしのカギ』だと!? しかたない、ゆるす…!」" },
        { msg: "* やみのへいしは みちを あけた" },
        { flag: "gateOpen" },
      ];
    }
    return [{ msg: "やみのへいし「ここから さきは とおさん。『ゆるしのカギ』なくして ゆるされると おもうな」" }];
  },

  boss_zannen(g) {
    if (g.flags.cleared) return [];
    return [
      { msg: "ザンネン「よくぞ ここまで来た、ロイヤルニートども…。だが ざんねん!せかいの はかいは もう とめられん!」" },
      {
        battle: ["zannen"],
        win: [
          { msg: "ザンネン「ば、ばかな…わたしが やぶれるとは…。だが ざんねん!ほんとうの きょうふは これからだ!」" },
          { msg: "* ザンネンのからだが くずれ、その おくから きょだいな かげが あらわれた…!" },
          {
            battle: ["gudaguda"],
            win: [
              { msg: "* はかいしんグダグダは ちりとなって きえていった…!" },
              { msg: "* せかいに へいわが もどった!" },
              { flag: "cleared" },
              { warp: { map: "castle1", x: 6, y: 4 } },
              { msg: "王さま「おお、ガンバ、ノンビ、ミャーコ!でかしたぞ!そなたらに『モドキのくんしょう』を さずける!」" },
              { msg: "ノンビ「これで こころおきなく 寝られますね」 ミャーコ「またねこに もどりたいかも…じゆうだったわ…」" },
              { msg: "王さま「ところで このぼうけん、『II』というからには『I』が あったのでは…?」" },
              { msg: "王さま「……それは ふれない やくそくじゃ」" },
              { ending: true },
            ],
          },
        ],
      },
    ];
  },

  chest_herosw() {
    return [{ learnEquip: "herosw" }];
  },
  chest_plate() {
    return [{ learnEquip: "plate" }];
  },

  shop_rirefu: () => [{ shop: "rirefu" }],
  shop_nonbiria: () => [{ shop: "nonbiria" }],
  shop_oar: () => [{ shop: "oar" }],
  inn_rirefu: () => [{ inn: 6 }],
  inn_oar: () => [{ inn: 20 }],
};

/* 現在の目的(クエストログ・QoL) */
function currentObjective(g) {
  if (g.flags.cleared) return "せかいは すくわれた!";
  if (g.flags.gateOpen) return "じゃしんかんザンネンを たおせ";
  if (g.flags.hasKey) return "みなみの島の ザンネンのしろへ(ふねで)";
  const crests = ["crestBrave", "crestKind", "crestNap"].filter((f) => g.flags[f]).length;
  if (crests >= 3) return "きたのほこらの 仙人に ご紋章を見せよ";
  if (!g.flags.quest) return "ガンバリアじょうの 王さまに会う";
  if (!g.flags.nonbiJoined) return "みなみの ノンビリアじょうで なかまをさがす";
  if (!g.flags.myakoJoined) return "にしのはいきょの ねこに会う(ご紋章 " + crests + "/3)";
  if (!g.flags.hasShip) return "みなとまちオールで ふねを手に入れる(ご紋章 " + crests + "/3)";
  return "3つのご紋章をあつめる(" + crests + "/3)…どうくつ・とう";
}
