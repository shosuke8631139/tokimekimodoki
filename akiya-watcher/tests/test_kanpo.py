"""官報チェック便のテスト。ネットワークは一切使わない(リンク生成のみ)。"""
import datetime

from akiya_watcher.kanpo import digest_lines, issue_toc_url, weekday_issues
from akiya_watcher.main import build_digest


def test_目次URLは日付から機械的に決まる():
    url = issue_toc_url(datetime.date(2026, 7, 21))
    assert url == "https://www.kanpo.go.jp/20260721/20260721.fullcontents.html"


def test_平日だけがリンク対象になる():
    # 2026-07-26 は日曜。直近7日 = 7/20(月)〜7/24(金) の5日が平日
    days = weekday_issues(datetime.date(2026, 7, 26), lookback_days=7)
    assert [d.day for d in days] == [24, 23, 22, 21, 20]
    assert all(d.weekday() < 5 for d in days)


def test_チェック便の本文にリンクと手順が入る():
    lines = digest_lines(datetime.date(2026, 7, 26))
    text = "\n".join(lines)
    assert "官報チェック便" in text
    assert "裁判所" in text
    assert "相続財産清算人" in text
    assert text.count("fullcontents.html") == 5  # 平日5日分
    assert "手順書" in text


def test_ダイジェストに官報チェック便が合流する():
    text = build_digest([], offer_min_age_days=90, kanpo_enabled=True)
    assert "官報チェック便" in text


def test_設定でオフにできる():
    text = build_digest([], offer_min_age_days=90, kanpo_enabled=False)
    assert "官報チェック便" not in text


def test_平日の今日の官報チェックにリンクとチュートリアルが入る():
    from akiya_watcher.kanpo import daily_lines
    lines = daily_lines(datetime.date(2026, 7, 24))  # 金曜
    text = "\n".join(lines)
    assert "今日の官報チェック" in text
    assert "20260724.fullcontents.html" in text
    assert "相続財産清算人" in text
    assert "スクショ" in text


def test_土日はお休みの案内だけになる():
    from akiya_watcher.kanpo import daily_lines
    lines = daily_lines(datetime.date(2026, 7, 25))  # 土曜
    assert len(lines) == 1
    assert "お休み" in lines[0]


def test_生存報告に今日の官報チェックが載る():
    from akiya_watcher.main import build_heartbeat
    text = build_heartbeat([], kanpo_enabled=True)
    assert "官報" in text
    text_off = build_heartbeat([], kanpo_enabled=False)
    assert "官報" not in text_off
