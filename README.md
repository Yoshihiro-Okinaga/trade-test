# trade-test

最終整理: **2026-08-31**

FX・CFD・株式の価格データを使い、Ref銘柄の情報がTarget銘柄の
将来値動きに残るかを検証する研究プロジェクトです。

現在は**新しい研究を停止し、プロジェクトを整理した状態**です。
再開するときは、このREADME・`RESEARCH_HYPOTHESES.md`・プロジェクト全体を
読めば現在地から続けられるようにしています。

---

## 1. 重要な方針

研究は次の順番を守ります。

```text
過去で探索
→ developmentで確認
→ 条件を固定
→ final OOS
```

final OOSを見た後に同じ期間へ合わせてルールを変更しません。
Regime / direction / volatilityなどの追加filterは、base strategyとは
**別仮説**として扱います。

現在、本番投入できる戦略はありません。

---

## 2. 現在必要なプログラム

```text
trade-test/
├── research/
│   ├── pair_research.py
│   ├── pair_research_config.py
│   ├── pair_statistics.py
│   ├── regime_research.py
│   └── parameter_plateau.py
├── stock-data/                 # 市場データ。削除しない
├── backtest.py
├── backtest_config.py
├── config.toml
├── config_plateau_is.toml
├── config_plateau_development.toml
├── market_data.py
├── regression_test.py
├── strategy_screening.py
├── strategy_task.py
├── walkforward.py
├── walkforward_config.py
├── walkforward_fold.py
├── README.md
└── RESEARCH_HYPOTHESES.md
```

役割:

- `strategy_screening.py` — StrategyTaskを広く探索してランキングを作る。
- `walkforward.py` — 過去だけで選抜し、未知期間へ順次適用する。
- `research/parameter_plateau.py` — ISとdevelopmentを比較し、現在の
  robustness条件を満たす候補を抽出する。
- `research/pair_research.py` — Pairの相関・cointegration・平均回帰研究。
- `research/regime_research.py` — 固定済みstrategyの市場環境依存を調べる。

特定銘柄専用の過去研究スクリプトやfinal OOS専用スクリプトは削除しました。
重要な結果だけを `RESEARCH_HYPOTHESES.md` に残しています。

---

## 3. CSVの扱い

**研究結果CSVはプロジェクトに保存しません。**
必要なときにPythonから再生成します。

削除してよいもの:

```text
trade_ranking*.csv
live_signals.csv
pair_research*.csv
regime_*.csv
parameter_plateau_*.csv
その他、研究スクリプトが生成した結果CSV
```

削除してはいけないもの:

```text
stock-data/**/*.csv
```

`stock-data/` のCSVは研究結果ではなく入力データです。

生成物は `results/` や専用結果フォルダへ出し、Git管理しません。

---

## 4. 通常実行

### Regression test

```bat
py -3.14 regression_test.py
```

### Strategy Screening

```bat
py -3.14 strategy_screening.py --config config.toml --save-dir results\screening
```

### Walk-forward

```bat
py -3.14 walkforward.py --config config.toml --save-dir results\walkforward
```

### Pair Research

`config.toml` の `[pair_research]` を設定してから:

```bat
py -3.14 research\pair_research.py --config config.toml --save-dir results\pair
```

### Regime Research

`config.toml` の `[regime_research].pairs` を設定してから:

```bat
py -3.14 research\regime_research.py --config config.toml --save-dir results\regime
```

---

## 5. Parameter Plateau

現在のbase strategy用robustness gateは暫定的に次です。

```text
2001–2015 IS
    center trade_count >= 150
    IS t >= 2.0
    neighbor_worst_t >= 1.0

2016–2020 development
    同じStrategyTaskを固定
    average_pct > 0
```

これはranking formulaではなく、尖った一点だけのstrategyを落とすためのgateです。
`neighbor_worst_t >= 1.0` は今後、既に見たfinal OOSへ合わせて変更しません。

再生成手順:

```bat
py -3.14 strategy_screening.py ^
  --config config_plateau_is.toml ^
  --save-dir results\plateau_is

py -3.14 strategy_screening.py ^
  --config config_plateau_development.toml ^
  --save-dir results\plateau_development

py -3.14 research\parameter_plateau.py ^
  --is-ranking results\plateau_is\trade_ranking_full.csv ^
  --development-ranking results\plateau_development\trade_ranking_full.csv ^
  --output-dir results\parameter_plateau
```

---

## 6. 現在地 / 再開地点

研究はここで停止しています。

再開時は、まず結果CSVを上記手順で再生成します。その後、
`parameter_plateau_candidates.csv` から、strategy-specific 2021–2025を
まだ消費していない候補を整理します。

**すぐに2021–2025を開かないこと。**
候補と判定条件を固定してから次の1本へ進みます。

過去の有力・失敗仮説とholdout状況は
`RESEARCH_HYPOTHESES.md` を参照してください。
