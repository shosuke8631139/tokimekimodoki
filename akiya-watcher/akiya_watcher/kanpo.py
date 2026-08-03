"""官報チェック便 — 週次ダイジェストに官報目次への直行リンクを添える。

背景 (2026-07 接続テストの結論):
  - 官報発行サイト (www.kanpo.go.jp) は robots.txt と利用ルールで
    クローラによるデータ収集を明確に禁止している。自動巡回はしない。
  - 一方、目次ページのURLは日付から機械的に決まる
    (/YYYYMMDD/YYYYMMDD.fullcontents.html)。リンクの生成にアクセスは不要。
  - 「相続財産清算人」「破産管財人」「限定承認」の公告は、相続や破産で
    財産の整理が始まった手がかりになる。号外の「公告 > 裁判所」欄を目視する。

そこで「機械はリンクだけ作り、読むのは人間」という半自動にする。
官報は行政機関の休日(土日・祝日・年末年始)を除き毎日8:30発行。
土日は発行されないのでリンクから除外する。祝日は発行されないが、
祝日表を持たずリンクは出す(開くと見つからない旨が表示されるだけ)。
"""
from __future__ import annotations

import datetime

BASE_URL = "https://www.kanpo.go.jp"

# 官報で目視する言葉と、メールにそのまま載せる中学生向けの説明。
SEARCH_TERM_GUIDE = (
    (
        "相続財産清算人",
        "相続する人がいない家を、裁判所が選んだ人が片付けて売るためのお知らせ。",
    ),
    (
        "破産管財人",
        "借金を返せなくなった人や会社の財産を、裁判所が選んだ人が集めて売るためのお知らせ。",
    ),
    (
        "限定承認",
        "相続した財産より多い借金は引き受けない、と相続人が裁判所に伝えたお知らせ。",
    ),
)


def issue_toc_url(day: datetime.date) -> str:
    """その日の官報の全体目次ページのURL (アクセスはしない。組み立てのみ)。"""
    ymd = day.strftime("%Y%m%d")
    return f"{BASE_URL}/{ymd}/{ymd}.fullcontents.html"


def weekday_issues(end: datetime.date, lookback_days: int = 7) -> list[datetime.date]:
    """end から遡って lookback_days 日間のうち、平日(月〜金)だけを新しい順に返す。"""
    days = []
    for i in range(lookback_days):
        d = end - datetime.timedelta(days=i)
        if d.weekday() < 5:  # 0=月 … 4=金
            days.append(d)
    return days


def daily_lines(today: datetime.date | None = None) -> list[str]:
    """毎日の生存報告に載せる「今日の官報チェック」チュートリアル。

    官報は行政機関の休日(土日祝)は発行されない。土日はお休みの案内だけ返す。
    祝日は判定表を持たないため、リンクを出して「開けなければお休み」と案内する。
    """
    today = today or datetime.date.today()
    if today.weekday() >= 5:  # 土日
        return ["📜 今日の官報チェック: 土日は官報の発行がお休みです。また月曜に。"]
    return [
        "📜 今日の官報チェック (30秒。宝の地図は毎朝8:30に更新)",
        "1. 開く → " + issue_toc_url(today),
        "   (開けない日は祝日=官報お休み。それで終了です)",
        "2. ページを下へスクロールして「公告」の並びの「裁判所」を開く",
        "3. 次の3つを目で探す (機械が読めない画像なので目で)",
        *(f"   【{term}】= {meaning}" for term, meaning in SEARCH_TERM_GUIDE),
        "4. 近くに「鹿児島」か「宮崎」があれば手がかり! その場でスクショ →",
        "   Claudeとの会話に貼れば、解読と手紙の書き方まで案内します",
        "なければ今日は終了。「裁判所の公告自体がない日」も普通にあります。",
    ]


def digest_lines(today: datetime.date | None = None, lookback_days: int = 7) -> list[str]:
    """週次ダイジェストに足す「官報チェック便」の行を作る。

    リンクを開いて目次の「公告 > 裁判所」欄に、鹿児島・宮崎に関する
    「相続財産清算人」「破産管財人」「限定承認」があるかを目視する案内文。
    """
    today = today or datetime.date.today()
    days = weekday_issues(today, lookback_days)
    if not days:
        return []
    youbi = "月火水木金土日"
    lines = [
        "📜 官報チェック便 — 財産の整理が始まった家の手がかり探し (週1回・5分)",
        "",
        "官報は言葉が難しいので、次の3つだけ目で探せばOK:",
        *(f"【{term}】= {meaning}" for term, meaning in SEARCH_TERM_GUIDE),
        "この3つの近くに「鹿児島」か「宮崎」があれば、家や家財の整理前かを調べる手がかり。",
        "",
        "やり方 (1リンク1分):",
        "1. 下のリンクを開く (祝日の分は開けなくて正常 = その日は官報お休み)",
        "2. ページを下へスクロールし「公告」の並びの中の「裁判所」を開く",
        "3. 3つの言葉と「鹿児島/宮崎」を目で探す。なければ閉じて次へ",
    ]
    for d in days:
        lines.append(f"・{d.month}/{d.day}({youbi[d.weekday()]}) {issue_toc_url(d)}")
    lines += [
        "",
        "見つけたら: まずスクリーンショット (90日で消えるため)。その画像を",
        "Claudeとの会話に貼れば、その場で中身を分かりやすく解読し、",
        "清算人への手紙 (docs/清算人打診レター.docx) の書き方まで案内します。",
        "読み方の実例つき解説: docs/官報チェック手順書.html",
    ]
    return lines
