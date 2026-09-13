# trade-test

最終整理: **2026-09-13**

Ref銘柄の値動きからTarget銘柄の将来値動きを探す研究プロジェクトです。

現在、本番投入できる戦略はありません。
有望候補は条件を固定し、過去結果に合わせて後から調整しません。

## 1. 研究の基本ルール

```text
ISで探索
→ 条件を固定
→ Development
→ 条件を固定
→ Final OOS / Walk-forward
→ Forward観察
```

- OOSを見た後に同じ期間へ合わせてparameterを変更しない。
- `long-only`、signal除外、threshold変更などを後付けで採用しない。
- `no_overlap = true` を基本とする。
- t値は順位付けの目安であり、絶対的な有意性判定には使わない。
- 株式の `cost = 0` は実運用コストを含まない。小さいedgeは必ずコスト耐性を確認する。

## 2. 設定ファイル

設定は3ファイルに分割しています。

```text
config.toml       実験ごとに変更する設定
symbols.toml      銘柄・group・cost・swap。基本固定
walkforward.toml  Walk-forward専用設定
```

読み込み時は単純にマージします。
旧来の1ファイル構成も利用できます。

主に触るのは `config.toml` です。

## 3. 主なファイル

```text
backtest.py              売買計算
backtest_config.py       共通設定
market_data.py           市場データ・指標計算
strategy_task.py         StrategyTask生成
strategy_screening.py    全組み合わせのランキング
walkforward.py           Walk-forward / live
walkforward_config.py    Walk-forward設定
walkforward_fold.py      Walk-forward期間
config.toml              実験設定
symbols.toml             銘柄定義
walkforward.toml         Walk-forward設定
RESEARCH_HYPOTHESES.md   研究結果と候補
stock-data/              入力データ
```

## 4. 実行

Strategy Screening:

```bat
py -3.14 strategy_screening.py --config config.toml
```

Walk-forward:

```bat
py -3.14 walkforward.py --config config.toml
```

Regression test:

```bat
py -3.14 regression_test.py
```

## 5. 現在の有望候補

詳細は `RESEARCH_HYPOTHESES.md` に記録します。

| 組み合わせ | 状態 | 要点 |
|---|---|---|
| `AUD_USD <- GBP_CHF / counter` | **B / Forward観察** | 2016–2020 Development PASS、2021–2025 Final OOS PASS |
| `6752_パナソニック <- USD_JPY` | **研究継続** | Breakout trend / hold=2 が固定後の2021–2025でプラス維持 |
| `9504_中国電力 <- AUD_NZD / counter` | **研究継続** | 2016–2020 Walk-forwardで5年すべて選抜、全体プラス |
| `9504_中国電力 <- AUD_USD / counter` | **保留** | 2フォールドともプラスだが12 tradesのみ |
| `COPPER / OIL 2.5σ extreme Pair` | **B / Forward観察** | 大乖離後の収束。サンプルが少ない |
| `EUR_GBP -> 複数FX` | **B / 保留** | Developmentでbreadthは残ったがedgeは減衰 |
| `AUD_NZD -> JPY crosses` | **未完了 / 凍結** | 仮説は残すが旧手順のまま再開しない |
| `OIL <- GOLD × OIL down` | **B- / 特徴量候補** | 売買戦略ではなくRegime特徴として残す |

## 6. 結果ファイル

研究結果CSVは必要に応じて再生成します。
`stock-data/**/*.csv` は入力データなので削除しません。

最新の判断は常に `RESEARCH_HYPOTHESES.md` を優先します。
