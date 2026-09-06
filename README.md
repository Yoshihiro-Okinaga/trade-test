# trade-test

最終整理: **2026-09-06**

FX・CFD・株式の価格データを使い、Ref銘柄の情報がTarget銘柄の
将来値動きに残るかを検証する研究プロジェクトです。

**Signal Consensus研究ラウンド1は凍結済み**です。2001–2015 ISで作った候補を
事前固定の順で6本まで2016–2020 Developmentへ送り、1本だけがPASSしました。
その `AUD_USD <- GBP_CHF / counter` は固定6 Taskのまま2021–2025 Final OOSもPASSし、
総合B・条件固定のforward観察候補としています。同じIS母集団から7件目は追加しません。

---

## 1. 重要な方針

研究は次の順番を守ります。

```text
ISで探索・構造確認
→ 条件を固定
→ developmentで確認
→ final条件を固定
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
│   ├── hold_response.py
│   ├── signal_consensus.py
│   ├── development_panel.py
│   ├── final_oos_panel.py
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
- `research/hold_response.py` — IS rankingからholdごとの平均損益を並べ、
  signalの時間応答・鮮度・持続性を整理する。
- `research/signal_consensus.py` — hold responseをTarget/Ref単位にまとめ、
  signal横断の方向一致・Event shape再現性を整理する。
- `research/development_panel.py` — 固定済みTaskパネルだけを2016–2020で評価する。
- `research/final_oos_panel.py` — Development PASS済みパネルだけを2021–2025で評価する。
- `research/parameter_plateau.py` — ISとdevelopmentを比較し、現在の
  robustness条件を満たす候補を抽出する。
- `walkforward.py` — 過去だけで選抜し、未知期間へ順次適用する。
- `research/pair_research.py` — Pairの相関・cointegration・平均回帰研究。
- `research/regime_research.py` — 固定済みstrategyの市場環境依存を調べる。

特定銘柄専用の過去研究スクリプトは削除しました。
Development / Final OOSは銘柄専用コードではなく、固定Taskパネルを入力にする
共通スクリプトへ統一しています。重要な結果は `RESEARCH_HYPOTHESES.md` に残します。

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
hold_response_*.csv
signal_consensus_*.csv
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

## 5. Signal Lifetime / Hold Response

現在の研究では、hold_daysを通常のparameterと同じように
「隣の値でも強いか」だけで評価しません。

短期signalでは5日と8日の差は大きく、100日と103日の差は小さいためです。
holdは**時間応答**として扱います。

### Signal class

```text
Event
    macd
    streak
    breakout

State
    change
    sma
    bb
    rsi
    di
    stoch
```

- Event — 発生した瞬間の情報。数日で鮮度が落ちても不自然ではない。
- State — 現在の市場状態。数週間にわたり効果が持続する可能性がある。

この分類はfinalなPASS/FAIL条件ではありません。
ただしDiscoveryの見方はsignal classで分けます。

```text
Event
    hold 1, 2, 3, 4, 5 の短期窓を見る
    trade_count条件を満たすholdの中で最大tを観察用代表値にする

State
    hold 1を固定anchorとして見る
```

Eventは発火当日に最大効果が出るとは限らないため、hold=1だけを
Discovery目印にすると2～5日で立ち上がる短命なsignalを見落とすためです。
短期窓の最大tは**最終holdの選抜ではありません**。

### IS用の推奨hold grid

```text
1, 2, 3, 4, 5, 7, 10, 20, 30
```

Signal Lifetime研究では `no_overlap = false` を使います。
同じsignal / entry集合について、決済を何日後にした場合の平均損益かを
比較しやすくするためです。

長いholdではリターン区間が互いに重なるため、通常の`t_value`は
独立標本としての有意性を過大評価する可能性があります。
そのためhold responseでは**average_pctのカーブを主に見て、t_valueは補助**とします。

### Hold Response実行

1つのrankingなら（`--ranking`には実際に存在するCSVパスを指定）:

```bat
py -3.14 research\hold_response.py ^
  --ranking trade_ranking_full.csv ^
  --output-dir results\hold_response
```

複数のsignal群を別実行した場合はrankingを複数指定できます。

```bat
py -3.14 research\hold_response.py ^
  --ranking <State側CSV> <Event側CSV> ^
  --output-dir results\hold_response
```

出力:

```text
hold_response_series.csv
hold_response_summary.csv
```

Discoveryの既定値:

```text
State anchor       hold = 1
Event short window hold = 1, 2, 3, 4, 5
min trades         150
Discovery t        2.0
```

必要なら `--discovery-hold` と `--event-discovery-holds` で変更できます。
ただしdevelopmentやfinalを見てから変更しません。

主な観察値:

- `discovery_mode` — `state_anchor` / `event_short_window`。
- `discovery_hold_spec` — Discoveryで見たhold範囲。
- `discovery_hold` — Eventでは短期窓内の観察用best-t hold、Stateでは固定anchor。
- `discovery_t_value` — 上記Discovery位置のt。最終hold選抜値ではない。
- `peak_hold` — 平均損益が最大になるhold。
- `t80_hold` — 最大平均損益の80%へ最初に到達するhold。
- `end_retention_ratio` — 最長holdの平均損益 / peak平均損益。
- `gain_pct_*` — 1→5、5→10、10→20、20→30で増減した平均損益。
- `marginal_pct_per_day_*` — 上記区間の1日あたり追加平均損益。
- `peak_left_ratio` / `peak_right_ratio` — peak周辺が孤立していないかを見る材料。

### Event response shape

Eventでは、短期Discovery窓の`average_pct`最大値を**短期ピーク**として、
hold 10 / 20 / 30でどの程度残る・伸びるかも観察します。
既定では短期ピークの±25%を「ほぼ同水準」の目安とします。

```text
fast_decay
    10 / 20 / 30日のうち少なくとも2点が短期ピークの75%未満で、
    30日も75%未満。後半に125%超の再伸長もない。

short_plateau
    125%を超える明確な伸長はなく、10 / 20 / 30日のうち
    少なくとも2点が短期ピークの75%以上を維持。

persistent
    hold 10の時点で短期ピークの125%を超えて伸びる。

late_extension
    hold 10では125%を超えないが、20または30日で125%を超えて再伸長。

mixed
    上記の単純な形に当てはまらない。
```

関連列:

- `response_shape` — 上記の観察用shape。Stateは`state_not_classified`。
- `response_shape_reason` — shapeを付けた理由。
- `event_early_peak_hold` / `event_early_peak_average_pct` — 短期ピーク。
- `event_retention_h10/h20/h30` — 各hold平均損益 / 短期ピーク平均損益。
- `response_material_ratio` — 「意味のある差」の観察幅。既定値0.25。

必要なら`--response-material-ratio`で観察幅を変更できますが、
developmentやfinalに合わせて調整するための値ではありません。

`discovery_pass`、`t80`、`response_shape`、これらの比率は現段階では
**finalな選抜gateではありません**。まずISだけでresponse curveの形を観察し、
ルールを固定してからdevelopmentへ進みます。

MACD / streak / breakoutは現行実装では`sma_period`に依存しません。
`hold_response.py` は、このために生成された重複系列を自動で1系列へ正規化します。

完全な`StrategyTask`を後で再現できるよう、出力には次の2列を分けて残します。

- `sma_period` — 分析上意味のあるSMA period。非依存signalでは空欄。
- `task_sma_period` — 実行用Taskへ戻すための元sma_period代表値。非依存signalでは重複した元Taskの最小値を決定的に採用。

`task_sma_period`はMACD / streak / breakoutの予測ロジックに影響する値ではありません。
完全な`StrategyTask`を再実行可能にするための実行上の代表値です。


---

## 6. Signal Consensus

`hold_response.py` の出力を `Target <- Ref` 単位にまとめ、
**signal定義を変えても同じ方向の関係が再現されるか**を観察します。

これは新しいranking scoreやPASS/FAIL gateではありません。
単一signalの最高tだけではなく、次を横並びにするための集計です。

- 何種類のsignalがDiscovery候補になったか。
- 順張り / 逆張りのどちらに何種類そろったか。
- 同じsignalが両方向で候補になる曖昧なケースがないか。
- StateとEventが同じ方向を示すか。
- Eventが複数ある場合、`response_shape`が似ているか。
- Target / Ref名に共通構成要素があるか。

現在の2つのHold Response結果をまとめる例:

```bat
py -3.14 research\signal_consensus.py ^
  --hold-response ^
    results\hold_response\hold_response_series.csv ^
    results\hold_response_streak_breakout\hold_response_series.csv ^
  --output-dir results\signal_consensus
```

入力する `hold_response_series.csv` は、同じIS期間・同じhold grid・
同じHold Response設定で作ったものに限ります。
同じsignal family代表が複数入力で異なる場合はエラーにして、
結果を黙って混ぜません。

出力:

```text
signal_consensus_pairs.csv
signal_consensus_details.csv
signal_consensus_tasks.csv
signal_consensus_summary.csv
```

主な観察列:

- `candidate_signal_count` — 方向を問わないDiscovery候補signal種類数。
- `trend_only_signal_count` / `counter_only_signal_count` — 一方向だけで候補になったsignal数。
- `bidirectional_signal_count` — 同じsignalが両方向で候補になった数。
- `consensus_direction` — 一方向だけのsignal数が多い側。同数なら`tie`。
- `consensus_signal_count` — consensus方向だけを示したsignal種類数。
- `direction_consistency_ratio` — consensus signal数 / 全候補signal数。
- `has_state_and_event_confirmation` — StateとEventがconsensus方向で両方あるか。
- `event_shape_mode` — consensus方向のEvent shape最頻値。複数同数なら併記。
- `event_shape_consistency_ratio` — Event shape最頻数 / Event候補数。
- `has_shared_component` / `shared_components` — symbol名を`_`で分けた共通要素。
- `signal_consensus_tasks.csv` — Discovery候補を完全な`StrategyTask`として再実行できる形で保存。

`signal_consensus_tasks.csv` のStrategyTask列:

```text
target
ref
signal_type
counter_trade
use_excess_return
threshold_width
hold_days
start_days
sma_period
```

`hold_days`にはISで固定した`discovery_hold`を使います。
`sma_period_relevant=false`のEvent signalでは、`sma_period`は実行互換の代表値であり、
そのsignal計算自体には使われません。

`has_shared_component` は共有通貨などを見つける簡易目印です。
経済的依存性を完全に判定するものではありません。

`consensus_signal_count`や`direction_consistency_ratio`も現段階では
**finalな選抜gateではありません**。ISで関係の再現性を整理する観察値です。

---

## 7. Parameter Plateau

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

ただし、**hold_daysは通常のparameter neighborとは別に扱います。**
Signal Lifetime研究でholdの時間応答を固定してから、threshold / sma_periodなどの
parameter robustnessと組み合わせます。

従来の再生成手順:

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

## 8. Frozen Development Panel

Developmentでは広いscreeningをやり直さず、`signal_consensus_tasks.csv`で
固定した1ペアのStrategyTaskパネルだけを評価します。

共通Development gate:

```text
全Taskを評価できる
average_pct > 0 が ceil(0.75 × Task数) 以上
Stateが1本以上ある場合、Stateで1本以上 positive
Eventが1本以上ある場合、Eventで1本以上 positive
Taskの average_pct 単純平均 > 0
```

`t_value`は記録しますがgateには使いません。
Development結果を見た後にsignal / threshold / hold / SMA / directionを選び直しません。

通常の`ranking_period`はentry年だけで集計するため、2020年末のトレードが
2021年に決済される可能性があります。専用評価ではholdoutを守るため、
**entry_dateとexit_dateの両方が2016–2020内にあるトレードだけ**を使います。
また、`backtest.calc_trade_results()`のcorrelationは全履歴で計算される補助値なので、
Development / Final OOSの専用CSVには出力しません。

### 1件目: EUR_CHF <- NZD_USD

4本固定、必要positive数は3/4。2016–2020 Developmentは4/4マイナスとなり
**REJECT**。条件変更や救済調整は行いません。

### 2件目: AUD_USD <- GBP_CHF — PASS

固定した6 StrategyTask:

```text
signal   class  counter  threshold  hold  start  sma
BB       State  true     1.0        1     1      50
Change   State  true     1.0        1     1      10
RSI      State  true     20.0       1     1      10
SMA      State  true     1.0        1     1      15
Stoch    State  true     30.0       1     1      15
Streak   Event  true     2.5        5     1      10
```

2016–2020 Development結果:

```text
Streak   +0.137695%   positive
BB       -0.008313%   negative
Change   +0.031179%   positive
RSI      +0.035777%   positive
SMA      +0.039140%   positive
Stoch    +0.016881%   positive

positive Task   5 / 6
State positive  4 / 5
Event positive  1 / 1
panel average   +0.042060%
```

事前固定gateをすべて満たしたため **Development PASS**。
Development結果を見てsignal / threshold / hold / SMA / directionは変更しません。

### 3件目: US30_Futures <- EUR_NZD — REJECT

固定4 Taskを2016–2020 Developmentで評価した結果、4/4がnegativeとなり
**Development REJECT**。救済調整は行いません。

```text
Breakout  -0.182124%  t -1.902535
MACD      -0.023891%  t -0.139846
Streak    -0.143626%  t -0.972921
BB        -0.287993%  t -1.470421

positive Task   0 / 4
State positive  0 / 1
Event positive  0 / 3
panel average   -0.159409%
```

### 残りDevelopment候補の固定キュー — 完了 / 凍結

Development結果を見て次候補を選び直すこと自体が選択バイアスになるため、
追加Developmentは事前に3候補だけへ固定し、順番を変更しませんでした。
これでSignal Consensus新手順のDevelopment検証は合計6候補で打ち切りです。

固定順:

```text
4. GBP_USD <- EUR_JPY / trend
5. GBP_CHF <- NZD_USD / counter
6. CAD_JPY <- GBP_CHF / counter
```

`EUR_USD <- TRY_JPY`などTRY_JPY Refは長期構造変化の懸念が強いため
標準キューとは別枠に置きました。EUR_GBP Refは過去のmulti-FX themeで
Development情報を既に一部消費しているため、新手順そのものの検証キューから外しました。

### 4件目: GBP_USD <- EUR_JPY — REJECT

共有componentなし。3 signalがすべてtrend方向に一致し、State 2 + Event 1。
事前固定した3 StrategyTaskをそのまま2016–2020 Developmentで評価しました。

```text
signal  class  counter  threshold  hold  start  sma   IS avg       IS t
Streak  Event  false    2.5        5     1      10    +0.117440%  3.094860
BB      State  false    1.0        1     1      50    +0.028374%  2.287219
Stoch   State  false    30.0       1     1      10    +0.027234%  2.034618
```

Development結果:

```text
Streak  n=339  avg -0.052439%  t -0.602310
BB      n=718  avg -0.003650%  t -0.145088
Stoch   n=550  avg +0.010456%  t +0.414805

positive Task   1 / 3
State positive  1 / 2
Event positive  0 / 1
panel average   -0.015211%
```

N=3なので事前gateは3/3 positive必須。条件を満たさず **REJECT**。
救済調整は行いません。

### 5件目: GBP_CHF <- NZD_USD — REJECT

共有componentなし、3 signalすべてcounter。State 1 + Event 2。
事前固定Task:

```text
Breakout  Event  counter  threshold=0.5  hold=4  start=1  sma=10
Streak    Event  counter  threshold=2.5  hold=5  start=1  sma=10
BB        State  counter  threshold=2.5  hold=1  start=1  sma=100
```

N=3の既存75% gateをそのまま適用し **Development REJECT**。
このREADMEには詳細Development数値を転記していません。
Task除外、hold / threshold / SMA / direction変更は行いません。

### 6件目: CAD_JPY <- GBP_CHF — REJECT

共有componentなし、3 signalすべてcounter。State 2 + Event 1。
事前固定Task:

```text
Breakout  Event  counter  threshold=0.5   hold=1  start=1  sma=10
SMA       State  counter  threshold=1.0   hold=1  start=1  sma=10
Stoch     State  counter  threshold=30.0  hold=1  start=1  sma=15
```

N=3の既存75% gateをそのまま適用し **Development REJECT**。
このREADMEには詳細Development数値を転記していません。
救済調整は行いません。

### Signal Consensus研究ラウンド1 — 凍結結果

事前に打ち切りを固定した6候補の結果:

```text
1. EUR_CHF <- NZD_USD / counter        Development REJECT
2. AUD_USD <- GBP_CHF / counter        Development PASS -> Final OOS PASS
3. US30_Futures <- EUR_NZD / trend     Development REJECT
4. GBP_USD <- EUR_JPY / trend          Development REJECT
5. GBP_CHF <- NZD_USD / counter        Development REJECT
6. CAD_JPY <- GBP_CHF / counter        Development REJECT
```

集計:

```text
Development PASS   1 / 6
Development REJECT 5 / 6
Final OOS対象      1 / 1
Final OOS PASS     1 / 1
```

このラウンドでは **追加の7件目を選ばない**。
同じ2001–2015 Signal Consensus母集団から別候補を後付けで掘り続けず、
この研究ラウンドをここで凍結します。
`AUD_USD <- GBP_CHF / counter` は条件固定のforward観察候補であり、
Final結果を見た後のsignal選別やパラメータ変更は行いません。

---

## 9. Frozen Final OOS Panel

Development PASSした `AUD_USD <- GBP_CHF / counter` の同じ6 Taskを、
2021–2025 Final OOSでそのまま評価します。

Final gateはDevelopmentと同じ条件を事前固定します。

```text
全Taskを評価できる
average_pct > 0 が ceil(0.75 × Task数) 以上
Stateで1本以上 positive
Eventで1本以上 positive
Taskの average_pct 単純平均 > 0
t_valueは記録のみでgateには使わない
```

N=6なので5/6以上positiveが必要です。EventはStreak 1本だけなので、
Streakがnegativeなら他の5本がpositiveでもREJECTです。

`research/final_oos_panel.py` は、PASS済みのDevelopment出力を入力にします。
Development summaryがPASSでない場合はfinalを実行しません。

Finalでも期間境界の未来価格を使わないため、**entry_dateとexit_dateの両方が
2021–2025内にあるトレードだけ**を評価します。2025年末entryが2026年に
exitするトレードは除外します。

実行:

```powershell
py -3.14 research\final_oos_panel.py `
  --development-tasks results\development_panel_aud_usd_gbp_chf\development_panel_tasks.csv `
  --development-summary results\development_panel_aud_usd_gbp_chf\development_panel_summary.csv `
  --config config.toml `
  --target AUD_USD `
  --ref GBP_CHF `
  --output-dir results\final_oos_panel_aud_usd_gbp_chf
```

出力:

```text
final_oos_panel_tasks.csv
final_oos_panel_summary.csv
final_oos_panel_trades.csv
```

Final結果を見た後に勝ったsignalだけを残す、hold / threshold / SMA / directionを
変更する救済調整はしません。

2021–2025 Final OOS結果:

```text
Streak   +0.099003%   positive
BB       +0.013316%   positive
Change   -0.017608%   negative
RSI      +0.001760%   positive
SMA      +0.026463%   positive
Stoch    +0.023616%   positive

positive Task   5 / 6
State positive  4 / 5
Event positive  1 / 1
panel average   +0.024425%
```

事前固定gateをすべて満たし **Final OOS PASS**。
ただしIS → Development → Finalでpanel edgeは縮小しているため、総合評価はB。
条件変更せずforward観察候補とし、Streakだけを後付け採用するなどの救済選別はしません。

---

## 10. 現在地 / 研究ラウンド凍結

1. 基本signalの2001–2015 IS screening — 完了。
2. Hold Response整理 — 完了。
3. Signal Consensus整理 — 完了。
4. Development候補を合計6本で打ち切り — 完了。
5. Development PASSは `AUD_USD <- GBP_CHF / counter` の1/6のみ。
6. 同じ6 Taskの2021–2025 Final OOS — **PASS / 総合B / forward観察**。
7. 残り5候補はDevelopment REJECT。救済調整なし。
8. **Signal Consensus研究ラウンド1を凍結。7件目は追加しない。**

次に研究を再開する場合は、この凍結済み母集団の続きを掘るのではなく、
**別仮説・別選抜方法を新しい研究ラウンドとして事前定義してから開始**します。

凍結中の唯一のforward観察候補:

```text
AUD_USD <- GBP_CHF / counter
評価: B
状態: Task / direction / threshold / hold / SMA固定
用途: paper / forward observation
```

**このラウンドの条件・候補数・結果を後から変更しないこと。**
