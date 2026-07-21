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
        "📜 官報チェック便 — 相続人がいない家を探す (週1回・5分)",
        "各リンクの目次で「公告 > 裁判所」を開き、鹿児島・宮崎の家庭裁判所の",
        "「相続財産清算人選任」公告がないか目で確認 (祝日分はリンク切れでOK):",
    ]
    for d in days:
        lines.append(f"・{d.month}/{d.day}({youbi[d.weekday()]}) {issue_toc_url(d)}")
    lines.append("見つけたら: docs/官報チェック手順書.html の手順で清算人へ手紙を1通。")
    return lines
