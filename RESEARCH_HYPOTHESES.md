# RESEARCH_HYPOTHESES

最終整理: **2026-09-06**

このファイルは、研究を続けるために必要な**結論だけ**を残します。
詳細CSVは保存せず、必要ならPythonから再生成します。

---

## 1. 現在の研究判断

```text
本番投入可能     なし
研究             Signal Consensus研究ラウンド1を凍結
Discovery        2001–2015 IS
Development      2016–2020（固定6候補を検証済み）
Development PASS 1 / 6
Final OOS        2021–2025（AUD_USD <- GBP_CHFで消費済み）
Final OOS PASS   1 / 1
forward候補      AUD_USD <- GBP_CHF / counter（総合B、条件固定）
次               同じ母集団は掘らず、新研究ラウンドを事前定義して開始
```

final OOSまで進めた過去研究では、IS/developmentで見えたedgeがfinalで
大きく縮む例が多く、従来の「best t-value 1本選抜」だけでは不十分でした。

過去監査の要点:

```text
final OOS監査対象          6
本番投入可                 0
final baseline平均プラス  4/6
final stress平均プラス    1/6
Regime優位方向維持        1/3
```

この反省から、parameterの最高点だけでなく、
**signal familyとhold方向の構造**をISで確認してからdevelopmentへ進む方法を1ラウンド検証しました。
6候補中5候補がDevelopmentで脱落したため、Signal Consensusは候補を絞る探索フィルタとして残し、
この母集団の追加掘りは行いません。

---

## 2. 現在のbase strategy仮説

Parameter Plateau研究から、暫定的なbase gateは維持します。

```text
IS 2001–2015
    center trade_count >= 150
    IS t >= 2.0
    neighbor_worst_t >= 1.0

Development 2016–2020
    exact frozen StrategyTask
    average_pct > 0
```

意味:

> best tが高いだけでなく、近いparameter設定も最低限強いstrategyを残す。

既にfinal OOSを消費した4戦略での監査では、Rule Bは
生存扱い2/2を残し、FAIL 2件中1件を事前に落としました。
ただしサンプルは小さく、成功を証明するものではありません。

**hold_daysは今後、通常のparameter neighborと同じには扱いません。**
短いholdでは数日の差が大きく、長いholdでは同じ数日の差が小さいためです。
holdはSignal Lifetime / Hold Responseで別に評価します。

Regime / direction / volatility filterはParameter Plateauでは検証できません。
追加する場合は独立した仮説としてdevelopment → finalをやり直します。

---

## 3. Signal Lifetime / Hold Response — 現在の方法仮説

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

暫定解釈:

- Eventは発生した瞬間の情報で、数日でedgeが減衰しても不自然ではない。
- Stateは現在の市場状態を表し、より長いholdまで関係が続く可能性がある。
- Event / State分類自体はPASS/FAIL条件ではない。

ISでの初期観察では、MACD・breakout・streakには短期で強くなり
その後減衰する系列が見られました。一方、change / SMA / BB / RSI / DI /
Stochには10～30日へ平均損益が蓄積する系列も多く見られました。
**まだdevelopmentでは確認していません。**

### Holdの評価

Signal Lifetime研究では:

```text
no_overlap = false
hold = 1, 2, 3, 4, 5, 7, 10, 20, 30
```

を基本とします。

見るもの:

- holdごとの `average_pct` response curve。
- peakへ向かう形と、その後の減衰・持続。
- `t80_hold` = 最大平均損益の80%へ最初に到達するhold。
- hold延長区間の1日あたり追加平均損益。
- peak前後が同方向か、孤立した一点になっていないか。

`t80`やresponse指標は現時点では**観察値**であり、選抜gateではありません。

Eventについては、短期Discovery窓の`average_pct`最大値を短期ピークとして、
hold 10 / 20 / 30の残存・再伸長から観察用`response_shape`も付けます。

```text
fast_decay      短期ピーク後に明確に減衰
short_plateau   短期ピーク付近を複数の後続holdでも維持
persistent      hold 10までに短期ピークを明確に上回って伸長
late_extension  hold 10では伸びず、20 / 30日で再伸長
mixed           単純な形に当てはまらない
```

既定では短期ピークの±25%を「ほぼ同水準」の観察帯とします。
この25%も`response_shape`も**選抜条件ではなく、ISカーブを整理するラベル**です。
developmentやfinalを見て調整しません。

長いholdではリターン区間が重なるため、通常の`t_value`は独立性を
過大評価する可能性があります。hold responseでは`average_pct`の形を主に見て、
`t_value`はDiscoveryの補助とします。

Discovery目印はsignal classで分けます。

```text
State
    hold = 1 を固定anchor
    trade_count >= 150
    t >= 2

Event
    hold = 1, 2, 3, 4, 5 の短期窓
    trade_count >= 150 を満たすholdの中で最大tを観察
    短期窓のどこかで t >= 2
```

Eventをhold=1だけで見ると、2～5日でedgeが立ち上がるbreakoutなどを
見落とすことが分かったため修正しました。Event短期窓の最大tは
**観察用代表値であり、最終holdの選抜ではありません**。
これらはISの候補を眺めるためのDiscovery目印で、finalなPASS条件ではありません。


---

## 4. Signal Consensus — 現在の観察方法

Hold Responseの`discovery_candidate`を `Target <- Ref` 単位にまとめ、
signal familyを変えても同じ方向が再現されるかを観察します。

見るもの:

```text
candidate_signal_count
trend_only_signal_count / counter_only_signal_count
bidirectional_signal_count
consensus_direction
consensus_signal_count
direction_consistency_ratio
State / Eventの同方向確認
Event response_shapeの一致
Target / Refの共通symbol要素
```

同じsignalが順張り・逆張りの両方でDiscovery候補になる場合は
`bidirectional`として扱い、方向consensusの票には入れません。

現在の2001–2015 IS結果を、State/MACD側とStreak/Breakout側の
Hold Response出力を統合して観察すると:

```text
Discovery候補ありTarget/Ref             278
複数signal候補あり                     95
同方向に2種類以上                      86
複数signalで方向が全て一致             79
State + Eventが同方向                  42
consensus方向にEventが2種類以上         34
```

これは**選抜gateではなくISの構造記録**です。
これらの件数や比率をdevelopment / finalを見て閾値化しません。

現時点で目立つ例:

- `GBP_USD <- EUR_GBP`: 8 signalが順張り。ただしGBPを共有。
- `AUD_USD <- EUR_GBP`: 7 signalが順張り、1 signalが逆張り。共有symbolなし。
- `GBP_USD <- GBP_CHF`: 7 signalが逆張り。ただしGBPを共有。
- `AUD_USD <- GBP_CHF`: 6 signalが逆張り。共有symbolなし。
- `EUR_CHF <- NZD_USD`: 4 signalが逆張り、State 2 + Event 2。共有symbolなし。
- `US30_Futures <- EUR_NZD`: 4 signalが順張り、State 1 + Event 3。共有symbolなし。

複数signal一致は独立した複数edgeとは数えません。
同じ価格系列を別変換したsignalは相関しているため、
**Ref→Target関係がsignal定義に依存しにくい可能性**として扱います。

### Development候補1 — EUR_CHF <- NZD_USD — REJECT

2001–2015 ISでState 2 + Event 2がすべてcounterで一致したため、4 Taskを固定して
2016–2020 Developmentへ進めた。事前gateは3/4以上positive、State/Event各1本以上positive、
panel平均positive。

Development結果:

```text
Breakout  n=594  avg -0.039482%  t -1.602
Streak    n=313  avg -0.015764%  t -0.454
BB        n=171  avg -0.012374%  t -0.538
SMA       n=390  avg -0.011164%  t -0.758
```

4/4マイナスで **REJECT**。hold / threshold / signal / directionの救済変更はしない。

### Development候補2 — AUD_USD <- GBP_CHF — PASS / Final OOSへ

2001–2015 ISだけを見た状態で、次の6 Taskを固定した。全てcounter、共有symbolなし。

```text
signal   class  threshold  hold  start  sma   IS avg       IS t
BB       State  1.0        1     1      50    +0.049196%  2.454681
Change   State  1.0        1     1      10    +0.063861%  3.006674
RSI      State  20.0       1     1      10    +0.076529%  3.267066
SMA      State  1.0        1     1      15    +0.067426%  2.386115
Stoch    State  30.0       1     1      15    +0.049594%  2.387052
Streak   Event  2.5        5     1      10    +0.153743%  2.517038
```

Development gateは前候補の結果を見て緩めず、4本時の3/4を一般化して固定した。

```text
全Taskを評価できる
positive Task数 >= ceil(0.75 × N)
Stateで少なくとも1本 positive
Eventで少なくとも1本 positive
panel average_pct > 0
t_valueはgateに使わない
```

2016–2020 Development結果（entry/exit両方が期間内のトレードのみ）:

```text
Streak   +0.137695%
BB       -0.008313%
Change   +0.031179%
RSI      +0.035777%
SMA      +0.039140%
Stoch    +0.016881%

positive Task   5 / 6
State positive  4 / 5
Event positive  1 / 1
panel average   +0.042060%
```

事前固定gateを全て満たし **Development PASS**。

Final OOSは2021–2025。6 Taskと方向・threshold・hold・SMAは変更しない。
Final gateもDevelopmentと同じ条件をそのまま使った。

```text
全Taskを評価できる
positive Task数 >= 5 / 6
Stateで少なくとも1本 positive
Event（Streak）が positive
panel average_pct > 0
t_valueはgateに使わない
```

Final結果:

```text
Streak   +0.099003%
BB       +0.013316%
Change   -0.017608%
RSI      +0.001760%
SMA      +0.026463%
Stoch    +0.023616%

positive Task   5 / 6
State positive  4 / 5
Event positive  1 / 1
panel average   +0.024425%
```

事前固定gateを全て満たし **Final OOS PASS**。ただしpanel平均は
IS +0.07672% → Development +0.04206% → Final +0.02443% と縮小。
総合評価はB。条件変更せずforward観察候補とする。
Final結果を見た後のsignal選別・hold / threshold / SMA / direction変更は行わない。

### Development候補3 — US30_Futures <- EUR_NZD — REJECT

固定4 Taskを2016–2020 Developmentで評価した結果:

```text
Breakout  n=582  avg -0.182124%  t -1.903
MACD      n=105  avg -0.023891%  t -0.140
Streak    n=294  avg -0.143626%  t -0.973
BB        n=68   avg -0.287993%  t -1.470
```

4/4マイナス、panel平均 -0.159409%で **REJECT**。
Task除外、hold / threshold / SMA / direction変更は行わない。

### 残りDevelopment検証の固定キュー — 完了 / 凍結

Development結果を見て次候補を選び続けることによる選択バイアスを避けるため、
追加検証は3候補に事前固定し、合計6候補で打ち切った。

```text
4. GBP_USD <- EUR_JPY / trend
5. GBP_CHF <- NZD_USD / counter
6. CAD_JPY <- GBP_CHF / counter
```

### Development候補4 — GBP_USD <- EUR_JPY — REJECT

共有componentなし。3 signalすべてtrend。State 2 + Event 1。
事前固定Task:

```text
signal  class  threshold  hold  start  sma   IS avg       IS t
Streak  Event  2.5        5     1      10    +0.117440%  3.094860
BB      State  1.0        1     1      50    +0.028374%  2.287219
Stoch   State  30.0       1     1      10    +0.027234%  2.034618
```

2016–2020 Development結果:

```text
Streak  n=339  avg -0.052439%  t -0.602310
BB      n=718  avg -0.003650%  t -0.145088
Stoch   n=550  avg +0.010456%  t +0.414805

positive Task   1 / 3
State positive  1 / 2
Event positive  0 / 1
panel average   -0.015211%
```

N=3なので3/3 positive必須。事前gateを満たさず **REJECT**。
救済調整は行わない。

### Development候補5 — GBP_CHF <- NZD_USD — REJECT

共有componentなし。3 signalすべてcounter。State 1 + Event 2。
事前固定Task:

```text
Breakout  Event  threshold=0.5  hold=4  start=1  sma=10
Streak    Event  threshold=2.5  hold=5  start=1  sma=10
BB        State  threshold=2.5  hold=1  start=1  sma=100
```

すべて `counter_trade=true`、`use_excess_return=false`。
既存75% gateを変更せず適用し **Development REJECT**。
詳細Development数値はこの仮説ファイルには転記していない。
Task除外、hold / threshold / SMA / direction変更は行わない。

### Development候補6 — CAD_JPY <- GBP_CHF — REJECT

共有componentなし。3 signalすべてcounter。State 2 + Event 1。
事前固定Task:

```text
Breakout  Event  threshold=0.5   hold=1  start=1  sma=10
SMA       State  threshold=1.0   hold=1  start=1  sma=10
Stoch     State  threshold=30.0  hold=1  start=1  sma=15
```

すべて `counter_trade=true`、`use_excess_return=false`。
既存75% gateを変更せず適用し **Development REJECT**。
詳細Development数値はこの仮説ファイルには転記していない。
救済調整は行わない。

### Signal Consensus研究ラウンド1 — 結論 / 凍結

固定した6候補の最終結果:

```text
1. EUR_CHF <- NZD_USD / counter        Development REJECT
2. AUD_USD <- GBP_CHF / counter        Development PASS -> Final OOS PASS
3. US30_Futures <- EUR_NZD / trend     Development REJECT
4. GBP_USD <- EUR_JPY / trend          Development REJECT
5. GBP_CHF <- NZD_USD / counter        Development REJECT
6. CAD_JPY <- GBP_CHF / counter        Development REJECT
```

```text
Development survival = 1 / 6
Final OOS tested     = 1 / 1
Final OOS PASS       = 1 / 1
```

観察:

- ISで複数signal・方向一致・State/Event確認まで揃えても、5/6はDevelopmentで脱落した。
- Signal Consensusは偽陽性を除き切るものではなく、候補を絞る探索フィルタとして扱う。
- 生き残った `AUD_USD <- GBP_CHF / counter` もISからFinalへedgeが縮小しており、
  production-readyとはみなさない。
- Final後にStreakだけを残すなどの後付け選別はしない。
- 7件目を追加せず、この2001–2015 Signal Consensus母集団の研究ラウンドを凍結する。

次に研究を始める場合は、同じ候補表の続きを掘るのではなく、
**新しい仮説・選抜規則・停止条件を事前固定した別ラウンド**として開始する。

---

## 5. 残している市場仮説

### COPPER / OIL 2.5σ extreme Pair — B / forward観察のみ

- 2001–2015で大乖離後の20日前後の収束現象。
- 2016–2020の固定ルールでは実売買ベースでもプラス。
- 2021–2025もstress後プラスだったが、15 closed tradesと少ない。
- medianはマイナスで、少数の大勝ちへの依存が強い。
- **実運用は見送り。条件変更せずforward観察候補。**

### EUR_GBP → 複数FX — B / 保留

固定Target:

```text
GBP_USD
AUD_USD
AUD_JPY
NZD_USD
EUR_USD
```

2016–2020 development:

```text
平均プラスTarget     4/5
equal-target平均     +0.136%
worst Target         -0.186%
```

breadthは弱く残ったが、2001–2015から大きく減衰。
DIを共有する4Targetはsignal日も共通で、独立edge 5本とは数えない。
**B・保留。finalへ急がない。**

今回のIS再確認では、特に `AUD_USD <- EUR_GBP` が複数の基本signalで
同方向に現れています。これは独立した複数edgeとは数えず、
**Ref→Target関係がsignal定義に依存しにくい可能性**として記録します。
新しいdevelopment判定にはまだ使いません。

### AUD_NZD → JPY crosses — 未完了 / 凍結

固定予定Target:

```text
EUR_JPY
CAD_JPY
CHF_JPY
GBP_JPY
```

研究方法を見直したため途中で停止。
再開する場合も、旧テーマ研究をそのまま続けるのではなく、
現在のSignal Lifetime / Hold Responseを含む共通手順を優先する。

### OIL ← GOLD × OIL down — B- / 特徴量候補

final 2021–2025でも `down > up` の相対差は残ったが、
down自体のbaseline平均はほぼ0、stressではマイナス。
**売買戦略としては見送り。Regime特徴としてのみ記録。**

---

## 6. 見送り・脱落

### OIL ← COPPER predictive — B- / 見送り

2016–2020では強かったが、2021–2025は大幅にedge縮小。
stress平均はマイナス。再チューニングしない。

### OIL ← SILVER × OIL down — FAIL

2021–2025でdown側がマイナスになり、down/up関係も逆転。
Parameter Plateau Rule Bでも事前REJECT側だった。
**脱落。**

### AUD_JPY ← EUR_GBP × AUD_JPY up — Regime FAIL

元strategyのparameter plateau自体は弱くなかったが、
事前仮説 `up > down` が2021–2025で逆転。
**Regime仮説を脱落。**

### Utility Pair portfolio — FAIL

中部/関西 + 中部/九州の固定50/50は2021–2025でterminal negative。
**脱落。**

---

## 7. Holdoutの扱い

- 2021–2025は複数研究ですでに部分的に見ている。
- OIL関連、AUD_JPY関連などは市場データとしてpristineとは呼ばない。
- 未消費候補でも「strategy-specific outcomeが未確認」かを区別する。
- finalを見た後のlong-only、方向変更、SMA変更、threshold変更などは採用しない。
- 2026以降をforward扱いする場合も、そのデータを既に見ていないか確認する。
- 新しいSignal Lifetime研究の条件は、2016–2020を見る前に固定する。

---

## 8. 現在地 / 凍結後

1. 2001–2015 IS screening — 完了。
2. Hold Response整理 — 完了。
3. Signal Consensus整理 — 完了。
4. 固定6候補のDevelopment — 完了。
5. Development PASSは `AUD_USD <- GBP_CHF / counter` の1/6のみ。
6. 同じ6 Taskの2021–2025 Final OOS — **PASS / 総合B / forward観察**。
7. 他5候補はDevelopment REJECT。救済調整なし。
8. **Signal Consensus研究ラウンド1を凍結。追加候補は掘らない。**

凍結中のforward観察候補:

```text
AUD_USD <- GBP_CHF / counter
評価: B
Task / direction / threshold / hold / SMA: 固定
```

次の研究は、この母集団の延長ではなく新しい研究ラウンドとして始める。
