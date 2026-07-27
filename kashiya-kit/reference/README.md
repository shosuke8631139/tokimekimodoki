# reference/ — 国交省 原本資料の置き場

テンプレートと原本の照合(逐語確認)のため、以下のファイルをダウンロードして
このフォルダに置いてください。ファイル名は下記に合わせてもらえると照合作業がスムーズです。

| # | 資料 | 入手先 | 保存ファイル名 |
|---|---|---|---|
| 1 | 家主向け DIY型賃貸借 実務の手引き | https://www.mlit.go.jp/common/001228736.pdf | `diy_jitsumu_tebiki.pdf` |
| 2 | DIY型賃貸借に関する契約書式例(2者間のもの。Word版でも可) | https://www.mlit.go.jp/jutakukentiku/house/jutakukentiku_house_tk3_000046.html からリンクされる書式例 | `diy_shoshikirei.pdf`(または `.docx`) |
| 3 | 賃貸住宅標準契約書 平成30年3月版・連帯保証人型 | https://www.mlit.go.jp/common/001479827.pdf | `hyojun_rentai.pdf` |
| 4 | 賃貸住宅標準契約書 平成30年3月版・家賃債務保証業者型 | https://www.mlit.go.jp/common/001479824.pdf | `hyojun_hosho.pdf` |
| 5 | **定期賃貸住宅標準契約書**(デフォルトが定期借家のため重要) | https://www.mlit.go.jp/jutakukentiku/house/jutakukentiku_house_tk3_000030.html からリンクされるPDF | `hyojun_teiki.pdf` |

- 置いたらコミットしてプッシュしてください(国の公表資料なので、出典を明記すれば
  リポジトリに含めて問題ありません。本READMEの上記URLが出典表記を兼ねます)。
- その後、Claude に「reference の原本と照合して」と依頼すれば、
  条項単位の照合と差異一覧を作成します。
