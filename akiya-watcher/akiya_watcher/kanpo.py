"""官報チェック便 — 週次ダイジェストに官報目次への直行リンクを添える。

背景 (2026-07 接続テストの結論):
  - 官報発行サイト (www.kanpo.go.jp) は robots.txt と利用ルールで
    クローラによるデータ収集を明確に禁止している。自動巡回はしない。
  - 一方、目次ページのURLは日付から機械的に決まる
    (/YYYYMMDD/YYYYMMDD.fullcontents.html)。リンクの生成にアクセスは不要。
  - 家庭裁判所の「相続財産清算人選任」公告は号外の「公告 > 裁判所」欄に載る。
    相続人がいない家 = 家財が手つかずの可能性が高い、本プロジェクトの本命筋。

そこで「機械はリンクだけ作り、読むのは人間」という半自動にする。
官報は行政機関の休日(土日・祝日・年末年始)を除き毎日8:30発行。
土日は発行されないのでリンクから除外する。祝日は発行されないが、
祝日表を持たずリンクは出す(開くと見つからない旨が表示されるだけ)。
"""
from __future__ import annotations

import datetime

BASE_URL = "https://www.kanpo.go.jp"


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
        "3. 【相続財産清算人】の文字を目で探す (機械が読めない画像なので目で)",
        "4. 近くに「鹿児島」か「宮崎」があれば当たり! その場でスクショ →",
        "   Claudeとの会話に貼れば、解読と手紙の書き方まで案内します",
        "なければ今日は終了。「裁判所の公告自体がない日」も普通にあります。",
    ]


def digest_lines(today: datetime.date | None = None, lookback_days: int = 7) -> list[str]:
    """週次ダイジェストに足す「官報チェック便」の行を作る。

    リンクを開いて 目次の「公告 > 裁判所」欄 に鹿児島・宮崎の家庭裁判所の
    「相続財産清算人選任」があるかを目視する、という人間向けの案内文。
    """
    today = today or datetime.date.today()
    days = weekday_issues(today, lookback_days)
    if not days:
        return []
    youbi = "月火水木金土日"
    lines = [
        "📜 官報チェック便 — 「相続人がいない家」のお知らせ探し (週1回・5分)",
        "",
        "官報は言葉が難しいので、探す言葉は1つだけでOK:",
        "【相続財産清算人】。この言葉の近くに「鹿児島」か「宮崎」があれば当たり。",
        "意味: 「この住所の家は相続人がいないので、裁判所が選んだ弁護士が",
        "家も家財もまとめて売ってお金に変えます」という国のお知らせ。",
        "= 誰も形見分けしておらず、家財が手つかずで眠っている可能性が高い家。",
        "",
        "やり方 (1リンク1分):",
        "1. 下のリンクを開く (祝日の分は開けなくて正常 = その日は官報お休み)",
        "2. ページを下へスクロールし「公告」の並びの中の「裁判所」を開く",
        "3. 「相続財産清算人」と「鹿児島/宮崎」を目で探す。なければ閉じて次へ",
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
