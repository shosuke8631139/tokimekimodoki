# keihi-bot — LINE領収書 → マネーフォワード 自動記帳ボット

仲間がLINEに領収書の写真を送ると、OpenAI API(gpt-4o の画像読み取り)で内容を抽出し、
LINE上で確認・承認したあとマネーフォワードに登録するボットです。

```
[LINEに写真送信]
      │ Webhook(署名検証・二重処理防止)
      ▼
[画像取得] ──► [OpenAIで抽出: 日付/金額/支払先/科目/税率/confidence]
      │
      ▼
[LINEに読み取り結果+「登録する/しない」ボタンを返信]
      │ 「登録する」を押すと
      ▼
[マネーフォワードへ登録]
   ├─ csvモード(デフォルト): MF MEインポート用CSVに追記
   └─ apiモード: クラウド経費APIで経費明細を登録
```

## 設計上のポイント

- **即時登録しない**: 経理データなので、AIの読み取り結果は必ず人間が承認してから登録します。
  confidence が 0.7 未満のときは警告付きで返信します。
- **二重登録防止**: LINEのメッセージIDをSQLiteに記録し、同じ画像の再処理をスキップします。
  承認ボタンの二度押しも無効化されます。
- **マネーフォワード ME には公開APIがない** ため、デフォルトは MEの「CSVインポート」
  形式のファイルを生成する csv モードです。クラウド経費を契約している場合は
  `REGISTER_MODE=api` でAPI登録に切り替えられます。
- **推測で埋めない**: 読めない項目は null にするようプロンプトで強制し、
  領収書以外の画像は登録対象にしません(架空経費の防止)。

## セットアップ

```bash
cd keihi-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 値を埋める
```

必要な認証情報:

1. **LINE**: [LINE Developers](https://developers.line.biz/) で Messaging API チャネルを作成し、
   チャネルシークレットとチャネルアクセストークンを取得
2. **OpenAI**: APIキーを取得
3. **(apiモードのみ)マネーフォワード クラウド経費**: OAuth2アプリを登録し、
   リフレッシュトークンと事業所IDを取得。エンドポイントは
   [公式APIドキュメント](https://expense.moneyforward.com/api/index.html) で確認し、
   異なる場合は `MF_API_BASE` / `MF_TOKEN_URL` を上書きしてください。

## ローカルでの動作確認

```bash
set -a && source .env && set +a
uvicorn app.main:app --port 8000
# 別ターミナルで
ngrok http 8000
```

ngrok が発行した `https://xxxx.ngrok.io/callback` を LINE Developers の
Webhook URL に設定し、「検証」→ ボットに領収書写真を送って動作確認します。

## テスト

外部API(LINE / OpenAI / マネーフォワード)はすべてモックされており、
ネットワークなしで実行できます。

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## csvモードの取り込み方

承認のたびに `data/expenses.csv` に1行追記されます(支出はマイナス金額、UTF-8 BOM付き)。
マネーフォワード MEの「データ入出力 > CSVファイルインポート」から取り込んでください。

## 既知の制限・今後の改善候補

- 承認待ちデータに有効期限がない(古い pending の掃除は未実装)
- 領収書画像そのものの保存(電子帳簿保存法対応)は未対応
- グループで誰が承認したかの記録は未実装(event の userId を保存すれば可能)
