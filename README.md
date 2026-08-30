# trade-test

最終更新: **2026-08-30**

このプロジェクトは、FX・CFD・株式などの価格データから、

- Ref銘柄のシグナルがTarget銘柄の将来値動きに効くか
- 過去だけで選んだ戦略が未知期間でも残るか
- 2銘柄の相対価格に短中期の平均回帰があるか
- 戦略の強さが市場レジームによって変わるか

を段階的に研究するためのプロジェクトです。

---

# 1. 引き継ぎに必要な3点

新しいチャットでは次の3点だけあれば再開できます。

1. **trade-test プロジェクト一式**
2. **README.md（このファイル）**
3. **RESEARCH_HYPOTHESES.md**

新しいチャットでは、

> README.md と RESEARCH_HYPOTHESES.md を読んで、現在地から研究を再開してください。

と伝えればよいです。

役割は分けます。

```text
README.md
    プロジェクト構成
    研究ルール
    現在地
    次にやること

RESEARCH_HYPOTHESES.md
    銘柄ごとの有力仮説
    過去の結果
    弱くなった仮説
    脱落した仮説
```

---

# 2. 現在の主要構成

```text
trade-test/
├── research/
│   ├── pair_research.py
│   ├── pair_research_config.py
│   ├── pair_statistics.py
│   ├── pair_strategy_research.py
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

主な役割:

```text
strategy_screening.py
    予測型戦略の広い探索

walkforward.py
    過去だけで選抜 → 未知期間で検証

research/pair_research.py
    Pair候補の統計・平均回帰研究

research/pair_strategy_research.py
    Pair候補を実売買に近い形で検証

research/regime_research.py
    既存予測戦略の市場環境依存を研究
```

研究段階のロジックを、
安定している本体コードへ急いで混ぜない方針です。

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
- OOSを見たあとで都合よく条件を変更しない
- 最良の1パラメータだけを信用しない
- 複数期間での再現を重視する
- 平均だけでなく中央値・勝率・取引数を見る
- 高相関だけでPairを採用しない
- ADF / cointegrationだけでPairを採用しない
- 同じRefやTargetへの集中を独立edgeと数えない
- 研究用edgeと実際の投資P&Lを混同しない
- 最終ホールドアウトで失敗したら、その結果を受け入れる

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

基盤は完成しています。

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

`max_open_positions` の大規模な再設計は保留です。

---

# 6. Pair Research

Pair Research は通常の予測型とは別研究です。

```text
2銘柄の相対価格が大きく乖離
↓
短中期で縮小するか
```

という現象を調べました。

## 検証の流れ

```text
2001–2015
Discovery

2016–2020
2001–2015のalpha / betaを固定してdevelopment検証

売買ルールを固定

2021–2025
最終OOS
```

最終OOS前に固定した主な条件:

```text
Pair
    中部電力 / 関西電力
    中部電力 / 九州電力

hedge
    2001–2015 OLS固定

z-score
    60日

entry
    ±2σ
    signal翌営業日終値
    両方向

exit
    zero cross確認後の翌営業日
    最大20営業日

allocation
    中部/関西 50%
    中部/九州 50%

baseline cost
    10 bps / turnover
    short 0.5 bps / day

stress cost
    20 bps / turnover
    short 1.0 bps / day

return basis
    株式分割調整済み終値の価格リターン
    配当は含めない
```

電力株CSVには、

```text
調整後終値 なし
配当       なし
株式分割   あり
```

だったため、
2001–2020と評価条件を揃える目的で
配当を追加せず価格リターンで最終OOSを行いました。

---

# 7. Pair最終OOSの結論

## 2021–2025 Portfolio

```text
closed trades    41

gross
    terminal return   +1.09%
    CAGR              +0.22%

baseline
    terminal return   -3.81%
    CAGR              -0.77%

stress
    terminal return   -8.48%
    CAGR              -1.76%
```

最終OOS前に決めた判定基準では、

```text
baseline > 0 & stress > 0
    強く合格

baseline > 0 & stress <= 0
    合格だがコストに弱い

baseline <= 0
    不合格

closed trades < 20
    判断保留
```

でした。

したがって、

> **50/50 Pair Portfolio は最終OOS不合格。**

と正式に結論づけます。

## Pair別

### 中部電力 / 関西電力

2021–2025でもgrossとbaselineはわずかにプラスでしたが、
stressではマイナスでした。

```text
評価:
    weak positive
    実用edgeとしては弱い
    主力候補から降格
```

### 中部電力 / 九州電力

2021–2025ではgrossからマイナスでした。

```text
評価:
    最終OOS失敗
    現在のPair戦略候補から脱落
```

## Pair研究で今後やらないこと

2021–2025の結果を見て、

```text
60日 → 90日
2σ → 1.8σ
20日 → 15日
上側だけ売買
九州を外す
関西だけにする
```

などへ変更して、
同じ2021–2025を「最終OOS」として再評価しません。

2021–2025はすでに見たため、
今後この期間を使った変更は新しいdevelopment研究になります。

**2026年は今回の最終OOSには使っていません。**

---

# 8. Regime Research

既存予測戦略について、

> Targetの市場環境によって戦略の強さが変わるか

を研究します。

固定レジーム定義:

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

比較済み期間:

```text
2001–2005
2006–2010
2011–2015
2016–2020
```

現在はRegime条件を
本体の売買フィルタには組み込んでいません。

正常な `research/regime_research.py` は
複数 `periods` に対応し、

```text
regime_selected_strategies.csv
regime_trades.csv
regime_summary.csv
regime_comparison.csv
```

を出力します。

---

# 9. 現在の研究段階

```text
Strategy Screening
    候補探索済み

Walk-forward
    基盤完成

Pair Research
    Discovery
    ↓
    development
    ↓
    売買ルール固定
    ↓
    2021–2025 final OOS
    ↓
    不合格
    ↓
    現研究は終了

Regime Research
    20ペアへ拡張済み
    ↓
    4期間比較済み
    ↓
    OIL_USD ← GOLD_USD × OIL down を固定
    ↓
    2021–2025 final OOS
    ↓
    WEAK_PASS
```

`OIL_USD ← GOLD_USD × OIL down` は、
**Regime現象としては再現したが、売買戦略としては弱い**
という結論です。

2021–2025:

```text
OIL down
    closed trades       36
    baseline average    +0.029%
    baseline median     +0.324%
    baseline win rate   52.8%
    baseline t          +0.027
    stress average      -0.471%

OIL up
    baseline average    -0.541%

down - up
    average difference  +0.571%
```

つまり、

```text
Regime仮説
    down > up
    → final OOSでも再現

絶対edge
    baselineはほぼゼロ
    stressではマイナス
    → 実用戦略としては見送り
```

と正式に扱います。

2021–2025を見た後で、

```text
200日SMA → 150日
20日hold → 10日
shortを除外
threshold 1.0 → 1.2
```

などへ変更して、同じ期間をfinal OOSとしてやり直しません。

---

# 10. 次にやること

現在の最優先仮説は、

```text
AUD_JPY ← EUR_GBP
+
AUD_JPY が長期up regime
```

です。

固定Regime定義:

```text
AUD_JPY up
    前営業日のAUD_JPY終値
    >=
    前営業日のAUD_JPY 200日SMA
```

この仮説はこれまでの4区間で、

```text
2001–2005
2006–2010
2011–2015
2016–2020
```

すべて `up > down` でした。

2001–2015で固定された代表戦略は、

```text
signal          sma
threshold       1
sma_period      15
counter_trade   false
use_excess_return false
hold_days       20
start_days      1
```

です。

次はPair・OIL←GOLDと同じ手順で、

```text
既存戦略を固定
↓
2001–2020で実トレード単位のRegime差を再確認
↓
合否基準・コスト耐性を固定
↓
2021–2025 final OOSを一度だけ
```

と進めます。

`OIL_USD ← GOLD_USD × OIL down` は、
final OOSでRegime差自体は残りましたが、
実用的な絶対edgeが残らなかったため、
現在の主力候補から外します。

---

# 11. 今やらないこと

- Pairの2021–2025を再び最終OOSとして最適化する
- Pairの失敗を条件追加で無理に救済する
- OIL←GOLDの2021–2025を再び最終OOSとして最適化する
- OIL←GOLDをshort除外やSMA変更で後付け救済する
- Regimeの20 / 252 / 200を今回の結果に合わせて変更する
- RegimeをStrategy Screeningの総当たりパラメータへ追加する
- 弱い元戦略をRegime miningで救済する
- `max_open_positions` を大改造する
- コスト未反映の研究値を実収益とみなす

---

# 12. 主な実行コマンド

Windows / Python 3.14:

```bat
py -3.14 strategy_screening.py
py -3.14 walkforward.py
py -3.14 walkforward.py live

py -3.14 research\pair_research.py --config config.toml
py -3.14 research\pair_strategy_research.py --config config.toml
py -3.14 research\regime_research.py --config config.toml
py -3.14 research\regime_strategy_research.py --config config.toml
py -3.14 research\regime_strategy_final_oos.py --config config.toml
```

OIL←GOLD Regime final OOSの出力例:

```text
oil_gold_regime_final_oos_trades.csv
oil_gold_regime_final_oos_summary.csv
oil_gold_regime_final_oos_verdict.csv
```

Pair最終OOSの出力例:

```text
pair_strategy_final_oos_trades.csv
pair_strategy_final_oos_summary.csv
pair_strategy_final_oos_portfolio.csv
pair_strategy_final_oos_portfolio_summary.csv
```

---

# 13. コード変更時の方針

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

# 14. 新しいチャットでの再開方法

プロジェクト一式と、

```text
README.md
RESEARCH_HYPOTHESES.md
```

を渡して、

> README.md と RESEARCH_HYPOTHESES.md を読んで、現在地から研究を再開してください。

と伝える。

現在の再開地点は、

> **Pairはfinal OOS不合格。OIL←GOLD × OIL down はRegime差のみ再現し、売買戦略としては見送り。次は `AUD_JPY ← EUR_GBP × AUD_JPY up` を同じ厳格な手順で検証する。**

です。
