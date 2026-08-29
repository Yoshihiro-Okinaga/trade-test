# trade-test

最終更新: **2026-08-29**

このプロジェクトは、FX・CFD・株式などの価格データから、

- Ref銘柄のシグナルがTarget銘柄の将来値動きに効くか
- 過去だけで選んだ戦略が未知期間でも残るか
- 2銘柄の相対価格に短中期の平均回帰があるか
- 戦略の強さが市場レジームによって変わるか

を段階的に研究するためのプロジェクトです。

---

# 1. 引き継ぎに必要な3点

新しいチャットでは、次の3点だけあれば研究を再開できます。

1. **trade-test プロジェクト一式**
2. **README.md（このファイル）**
3. **RESEARCH_HYPOTHESES.md**

新しいチャットでは、

> README.md と RESEARCH_HYPOTHESES.md を読んで、現在地から研究を再開してください。

と伝えればよいです。

銘柄ごとの研究結果・有力仮説・弱くなった仮説は、
このREADMEではなく `RESEARCH_HYPOTHESES.md` に集約します。

---

# 2. 現在の主要構成

```text
trade-test/
├── research/
│   ├── pair_research.py
│   ├── pair_research_config.py
│   ├── pair_statistics.py
│   └── regime_research.py
├── stock-data/
├── backtest.py
├── backtest_config.py
├── config.toml
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

```text
strategy_screening.py
    予測型戦略の広い探索

walkforward.py
    過去だけで選抜 → 未知期間で検証

research/pair_research.py
    2銘柄の相対価格・平均回帰研究

research/regime_research.py
    既存予測戦略の市場環境依存を研究
```

研究段階のロジックを、安定している本体へ急いで混ぜない方針です。

---

# 3. 研究の基本原則

```text
広く探索
↓
現象確認
↓
候補を絞る
↓
条件固定
↓
未知期間検証
↓
単純戦略化
↓
コスト耐性
↓
ポートフォリオ評価
```

守ること:

- 未来情報を使わない
- OOSを見たあとで条件を都合よく微調整しない
- 1つの最高パラメータだけを信用しない
- 複数Signal・複数期間での再現を重視する
- 平均だけでなく中央値・勝率・取引数を見る
- 高相関だけでPairを採用しない
- ADF / cointegrationだけでPairを採用しない
- 同じRefやTargetへの集中を独立戦略と数えない
- 研究用edgeと実際の投資P&Lを混同しない

---

# 4. 通常の予測型戦略

基本構造:

```text
Refのシグナル
↓
次営業日以降にTargetへエントリー
↓
一定期間後のTargetリターンを評価
```

現在の主要設定:

```text
signal_type:
    change
    sma
    bb
    di
    stoch

hold_days = 20
start_days = 1
sma_period = 10 / 15 / 50 / 100 / 200
counter_trade = true / false
no_overlap = true
use_excess_return = false
ranking_period = 2001–2015
```

`use_excess_return=true` は全期間平均ドリフトを使うため、
厳密な未知期間評価では原則 `false` を使います。

有力な銘柄関係は `RESEARCH_HYPOTHESES.md` を参照してください。

---

# 5. Walk-forward

現在の主要設定:

```text
train_years = 8
test_years = 1
step_years = 1
mode = rolling

select_metric = worst_year_pct
select_per = target
select_top_k = 1
min_is_trades = 30
min_is_t = 2.0
max_open_positions = 5
```

`worst_year_pct` は現在の設定であり、
最良の選抜指標として確定したわけではありません。

実装済み:

- IS選抜
- OOSトレード
- 年別成績
- threshold scan
- equity / drawdown
- live selection
- OPEN / PENDING / recent CLOSED
- `live_signals.csv`

`max_open_positions` は現在、
ポートフォリオ全体の同時建玉数だけを制限しています。

Refクラスター、Targetクラスター、戦略間相関、リスク量を考慮した
ポートフォリオ設計はまだ保留です。

---

# 6. Pair Research

Pair Research は通常の予測型とは別研究です。

```text
2銘柄の価格関係
↓
相対価格が大きく乖離
↓
短中期で縮小するか
```

現在の検証構造:

```text
2001–2015
Discovery
↓
alpha / beta 推定

2016–2020
2001–2015のalpha / betaを固定して検証

↓
売買ルール固定

2021～
最終 untouched holdout
```

**Pair Researchでは2021年以降をまだ見ないこと。**

2016–2020は結果を候補選定にも使ったため、
今後は development data と考えます。

2021年以降は売買ルール固定後に一度だけ評価します。

本命・保留・脱落候補は `RESEARCH_HYPOTHESES.md` を参照してください。

---

# 7. Regime Research

既存予測戦略について、

> Targetの市場環境によって戦略の強さが変わるか

を研究します。

固定定義:

```text
Volatility:
    Targetの20日実現ボラ
    vs
    過去252日の20日ボラ中央値

Direction:
    Targetの前営業日終値
    vs
    前営業日の200日SMA
```

entry日の分類には前営業日までの情報しか使いません。

4期間比較:

```text
2001–2005
2006–2010
2011–2015
2016–2020
```

2001–2015の3区間は戦略選抜期間内なので独立OOSではありません。
2016–2020が選抜期間外です。

現在はレジームを本体の売買フィルタには組み込んでいません。

### regime_research.py の注意

`config.toml` は `periods = [...]` 形式です。

`research/regime_research.py` は
**複数 periods 対応版**を使うこと。

正常な最新版では次を出力します。

```text
regime_selected_strategies.csv
regime_trades.csv
regime_summary.csv
regime_comparison.csv
```

---

# 8. 現在の研究段階

```text
Strategy Screening
    候補探索済み

Walk-forward
    基盤完成

Pair Research
    本命2組まで絞り込み済み
    ↓
    単純売買ルール固定待ち
    ↓
    2021+ 最終OOSは未実施

Regime Research
    20ペアまで拡張済み
    ↓
    4期間比較済み
    ↓
    有望な固定レジーム仮説を抽出済み
    ↓
    本体統合は保留
```

---

# 9. 次にやること

現在の最優先作業はPair Researchです。

```text
中部電力 / 関西電力
中部電力 / 九州電力
```

について、

**2021年以降を見ないまま、単純な売買ルールを固定する。**

決める項目:

- hedge ratioの更新方法
- z-score lookback
- entry threshold
- exit条件
- 最大保有期間
- 2ペア同時発生時の扱い
- 売買コスト
- 空売り可否・貸株コスト

その後、2021年以降を最終ホールドアウトとして一度だけ評価します。

---

# 10. 今やらないこと

- Pairの2021年以降を見る
- 2016–2020を見てPair閾値を細かく調整する
- 2.01σ、2.07σのような一点最適化
- Regimeの20 / 252 / 200を結果に合わせて変更する
- Regimeを今すぐStrategy Screeningの探索パラメータにする
- 弱い戦略をRegime miningで無理に救済する
- `max_open_positions` を大改造する
- コスト未反映の研究値を実収益とみなす

---

# 11. 実行コマンド

Windows / Python 3.14:

```bat
py -3.14 strategy_screening.py
py -3.14 walkforward.py
py -3.14 walkforward.py live
py -3.14 research\\pair_research.py --config config.toml
py -3.14 research\\regime_research.py --config config.toml
```

---

# 12. コード変更時の方針

このプロジェクトでは **分かりやすさを最優先**します。

- 不要な変更をしない
- 既存コメントを理由なく削除しない
- 関数の責務を明確にする
- UI / ロジック / I/O / 状態を必要に応じて分離する
- データの流れと副作用を追いやすくする
- グローバル状態は必要最小限
- worker cache用グローバルは安易に消さない
- 変更ファイルをすべて列挙する
- 既存ロジックを変更した場合は回帰テストする
- 早すぎる抽象化を避ける

---

# 13. 新しいチャットでの再開方法

プロジェクト一式と、

```text
README.md
RESEARCH_HYPOTHESES.md
```

を渡して、

> README.md と RESEARCH_HYPOTHESES.md を読んで、現在地から研究を再開してください。

と伝える。

最優先の続きは、

> **中部電力/関西電力と中部電力/九州電力について、2021年以降を見ずに単純なPair売買ルールを固定する。**

です。
