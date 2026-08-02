"""GitHub Models の実地テスト: GITHUB_TOKEN だけで無料のAI採点ができるか。

卒業制作フェーズ1(物件よみとりAI)を APIキー・課金なしで実現するための偵察。
新旧2つのエンドポイントを試し、日本語の採点プロンプトにJSONで答えられるかを見る。
"""

from __future__ import annotations

import json
import os
import sys

import requests

TOKEN = os.environ.get("GITHUB_TOKEN", "")

PROMPT = """あなたは空き家物件の分析者です。次の物件説明文を読み、
「売主がこの物件を手放したがっている気配(困り気配)」を0〜100で採点し、
理由を日本語1行で述べてください。必ずJSONのみで答えること。
形式: {"score": 数値, "reason": "理由"}

物件説明文:
「相続のため売却します。家財道具が残ったままの現状渡しとなります。
遠方在住のため内見対応は週末のみ。値下げしました(300万円→150万円)。」"""

ENDPOINTS = [
    ("models.github.ai", "https://models.github.ai/inference/chat/completions",
     "openai/gpt-4o-mini"),
    ("azure旧経路", "https://models.inference.ai.azure.com/chat/completions",
     "gpt-4o-mini"),
]


def try_endpoint(name: str, url: str, model: str) -> bool:
    print("=" * 70)
    print(f"### {name} / model={model}")
    try:
        res = requests.post(
            url,
            headers={"Authorization": f"Bearer {TOKEN}",
                     "Content-Type": "application/json"},
            json={"model": model,
                  "messages": [{"role": "user", "content": PROMPT}],
                  "max_tokens": 200, "temperature": 0},
            timeout=60)
    except Exception as exc:  # noqa: BLE001
        print(f"!! 接続失敗: {exc}")
        return False
    print(f"status={res.status_code}")
    if res.status_code != 200:
        print(res.text[:600])
        return False
    body = res.json()
    content = body["choices"][0]["message"]["content"]
    print(f"応答: {content}")
    # JSONとして読めるか(コードフェンス付きにも耐える)
    cleaned = content.strip().strip("`").removeprefix("json").strip()
    try:
        parsed = json.loads(cleaned)
        print(f"→ JSON解釈OK: score={parsed.get('score')} "
              f"reason={parsed.get('reason')}")
        usage = body.get("usage", {})
        print(f"→ トークン使用: {usage}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"!! JSON解釈失敗: {exc}")
        return False


def main() -> None:
    if not TOKEN:
        print("!! GITHUB_TOKEN が渡っていない")
        sys.exit(1)
    ok = False
    for name, url, model in ENDPOINTS:
        if try_endpoint(name, url, model):
            ok = True
            break
    print("=" * 70)
    print("結論: " + ("GITHUB_TOKENだけで採点できる ✅" if ok else "この経路は使えない ❌"))


if __name__ == "__main__":
    main()
