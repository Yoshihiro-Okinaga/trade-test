# RESEARCH_HYPOTHESES

最終更新: **2026-08-30**

このファイルは、`trade-test` で現在までに分かっている
**銘柄関係・市場現象・有力仮説**をまとめるための研究ノートです。

README.md にはプロジェクトの使い方と現在地だけを書き、
銘柄ごとの研究内容はこのファイルに集約します。

---

# 0. このファイルの読み方

評価は研究上の優先順位です。

```text
A+  最重要。次の検証へ進める価値が高い
A   かなり有力
B+  面白い。追加検証する価値あり
B   候補として残す
B-  追加検証候補
C   弱い / 優先度低い
保留  現象はあるが判断材料不足
脱落  現在は追わない
```

これは「利益が保証される順位」ではありません。

見出しに残っている `1.` `2.` などの番号は、
この研究ノート内での**仮説ID**です。
現在の優先順位は後半の「現時点の総合研究順位」を見てください。

特に、

- インサンプル
- 2016–2020のdevelopment OOS
- 2021–2025のfinal OOS
- Pairの研究edge
- 実際の売買P&L

は別物です。

---

# 1. Pair最終OOSと現在の最重要仮説

## 旧A+ → B-/C 1. 中部電力 / 関西電力の短中期relative-value回帰

### 元の仮説

> 中部電力と関西電力の相対価格が大きく乖離すると、
> 20日前後の短中期で乖離が縮小しやすい。

### 2001–2015 Discovery

```text
2σ → 20日edge平均    約 +1.350%
中央値                約 +1.063%
プラス率              約 59.7%
```

### 2016–2020 fixed_from_past

2001–2015で推定したalpha / betaを固定して、
2016–2020へそのまま適用。

```text
hedge ratio           約 0.8482
2σイベント            18回
20日edge平均          約 +1.455%
中央値                約 +1.616%
プラス率              約 61.1%
20日以内完全回帰      約 55.6%
```

この時点では非常に有力だった。

### 実売買に近づけた2016–2020 development

最終OOSを見る前に、次を固定した。

```text
z-score        60日
entry          ±2σ
execution      signal翌営業日終値
exit           zero cross確認後の翌営業日
max hold       20営業日
hedge          2001–2015 OLS固定
direction      両方向

baseline cost
    10 bps / turnover
    short 0.5 bps / day

stress cost
    20 bps / turnover
    short 1.0 bps / day
```

2016–2020:

```text
trades             20

gross average      +0.412%
gross median       +1.175%
gross win rate     65.0%

baseline average   +0.171%
baseline median    +0.926%
baseline win rate  65.0%

stress average     -0.070%
```

研究用spread edgeから実売買P&Lへ変えるとかなり薄くなったが、
baselineではまだプラスだった。

### 2021–2025 FINAL OOS

条件を変更せず、一度だけ最終OOSを評価。

```text
closed trades      23
open at period end 1

gross
    average         +0.381%
    median          +0.595%
    win rate        60.9%
    sleeve return   +8.365%

baseline
    average         +0.142%
    median          +0.349%
    win rate        60.9%
    t               +0.266
    sleeve return   +2.577%

stress
    average         -0.097%
    sleeve return   -2.915%
```

### 現在の正式評価

```text
B- / C
```

現象は完全には消えていないが、

- baseline edgeがかなり小さい
- stressではマイナス
- 主力戦略としての強さはない

ため、**A+候補から正式に降格**。

今後は本命として追わず、
structural breakやrelative-value研究の参考例として残す。

---

## 旧A+ → 脱落 2. 中部電力 / 九州電力の短中期relative-value回帰

### 元の仮説

> 中部電力と九州電力の相対価格も、
> 大きく乖離したあと20日前後で縮小しやすい。

### 2001–2015 Discovery

```text
2σ → 20日edge平均    約 +0.984%
中央値                約 +0.859%
プラス率              約 61.2%
```

### 2016–2020 fixed_from_past

```text
hedge ratio           約 0.8727
2σイベント            16回
20日edge平均          約 +0.953%
中央値                約 +1.126%
プラス率              約 56.3%
```

### 実売買に近づけた2016–2020 development

同じ固定ルールで、

```text
trades             20

gross average      +0.879%
gross median       +1.125%
gross win rate     70.0%
gross t            +1.98

baseline average   +0.635%
baseline median    +0.871%
baseline win rate  70.0%

stress average     +0.391%
```

と非常に強かった。

### 2021–2025 FINAL OOS

しかし、条件を一切変えずに最終OOSへ進めると、

```text
closed trades      18

gross
    average         -0.334%
    median          -0.657%
    win rate        44.4%
    sleeve return   -6.192%

baseline
    average         -0.575%
    median          -0.907%
    win rate        38.9%
    t               -1.168
    sleeve return   -10.199%

stress
    average         -0.816%
    sleeve return   -14.044%
```

となった。

### 現在の正式評価

```text
脱落
```

**コストを入れる前のgrossからマイナス**なので、
「コストが高すぎて消えた」のではない。

現在の単純Pair戦略としては、
2021–2025で平均回帰edgeが再現しなかったと判断する。

この結果を見て、

```text
2σ → 1.8σ
60日 → 90日
20日 → 15日
上側だけ売買
```

などへ変更して同じ2021–2025を再評価しても、
それは新しいdevelopment研究であり、
final OOSのやり直しとは扱わない。

---

## Pair Portfolioの最終結論

最終OOS前に、

```text
中部 / 関西  50%
中部 / 九州  50%
```

の固定sleeve方式も決めた。

### 2016–2020 development

```text
closed trades        40

gross
    terminal return  +13.321%
    CAGR             +2.533%

baseline
    terminal return  +7.978%
    CAGR             +1.547%

stress
    terminal return  +2.875%
    CAGR             +0.568%
```

### 2021–2025 FINAL OOS

```text
closed trades        41

gross
    terminal return  +1.087%
    CAGR             +0.216%

baseline
    terminal return  -3.811%
    CAGR             -0.774%

stress
    terminal return  -8.480%
    CAGR             -1.757%
```

final OOS前に決めた判定基準は、

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

だった。

したがって、

> **50/50 Pair Portfolio は正式に最終OOS不合格。**

Pair本命2組を中心とした研究はここで一区切りとする。

重要な教訓:

> Discoveryと最初のOOSで強くても、
> 売買ルールを固定した本当の未知期間でedgeが消えることはある。

これは失敗を隠すのではなく、
**最終ホールドアウトが正しく機能した例**として残す。

---

## 旧A+ → B- 3. GOLD_USD → OIL_USD × OIL down

表記:

```text
OIL_USD ← GOLD_USD
```

### 元の予測戦略

2001–2015で選ばれた代表戦略:

```text
signal          sma
threshold       1
sma_period      200
counter_trade   false
use_excess_return false
hold_days       20
start_days      1

IS trades       192
IS average      約 +2.057% / trade
IS t            約 2.98
```

2016–2020の元戦略:

```text
trades          67
平均            約 +2.094%
中央値          約 +4.610%
勝率            約 59.7%
```

### Regime仮説

TargetであるOILが、

```text
前営業日終値 < 前営業日200日SMA
```

の **down regime** のとき、
GOLD → OIL戦略が特に強い、という仮説。

2001–2020の実トレード再確認:

```text
期間          all平均     down平均     up平均      down-up
2001–2005    +1.137%     +5.269%      +0.026%     +5.243%
2006–2010    +3.152%     +7.457%      +0.590%     +6.866%
2011–2015    +1.391%     +2.150%      +0.268%     +1.882%
2016–2020    +2.094%     +5.155%      -0.541%     +5.696%
```

**4/4期間で down > up。**

2001–2020のdown限定をまとめると、

```text
trades       112
平均         約 +4.694%
中央値       約 +5.286%
勝率         約 66.1%
t            約 4.12
```

long / shortの両方でdevelopment edgeが確認されたため、
final OOS前にlongだけへ絞ることはしなかった。

### 2021–2025 FINAL OOS

事前固定条件:

```text
strategy
    sma / threshold=1
    sma_period=200
    counter_trade=false
    hold=20
    start=1
    long / short両方

regime
    OIL前営業日終値
    <
    OIL前営業日200日SMA

baseline
    既存OIL cost=0.03を使用

stress
    baseline損益からさらに0.5% / trade
```

事前判定結果:

```text
verdict = WEAK_PASS
```

2021–2025:

```text
全体
    trades             71
    baseline average   -0.252%

OIL down
    trades             36
    baseline average   +0.029%
    baseline median    +0.324%
    baseline win rate  52.8%
    baseline t         +0.027
    stress average     -0.471%

OIL up
    trades             35
    baseline average   -0.541%

down - up
    average difference +0.571%
```

### 現在の正式評価

```text
Regime現象:
    合格
    down > up はfinal OOSでも再現

売買戦略:
    見送り
    baseline edgeはほぼゼロ
    stressではマイナス

総合:
    B-
```

重要なのは、

> **「OIL downの方がOIL upより良い」という相対的なRegime差は
> final OOSでも残ったが、それだけでは十分な絶対収益にならなかった。**

という点。

Pair研究とは違い、
Regime現象自体が完全に消えたわけではない。

一方で、final OOSを見た後に、

```text
200日SMA → 150日
20日hold → 10日
shortを除外
threshold 1.0 → 1.2
強いdownだけ選別
```

などへ変更して同じ2021–2025を再評価しても、
それは新しいdevelopment研究であり、
final OOSのやり直しとは扱わない。

現在は主力候補から外し、
**Regime研究として有用な成功例 / 売買戦略としては弱い例**
として保存する。

---

# 2. 非常に有力な仮説

## 旧A → 脱落 4. EUR_GBP → AUD_JPY × AUD_JPY up

表記:

```text
AUD_JPY ← EUR_GBP
```

### 元戦略

2001–2015代表:

```text
signal          sma
threshold       1
sma_period      15
counter_trade   false
use_excess_return false
hold_days       20
start_days      1

IS trades       約 172
IS average      約 +0.909%
IS t            約 2.72
```

2016–2020の元戦略:

```text
trades          約 60
平均            約 +0.498%
中央値          約 +0.545%
勝率            約 58.3%
```

### Regime仮説

AUD_JPYが、

```text
前営業日終値 >= 前営業日200日SMA
```

の **up regime** で強いという仮説。

2001–2020の実トレード再確認では、

```text
期間          up平均       down平均      up-down
2001–2005    +0.115%      -0.630%      +0.746%
2006–2010    +2.500%      +1.637%      +0.862%
2011–2015    +1.220%      +0.075%      +1.146%
2016–2020    +0.766%      +0.342%      +0.424%
```

**4/4期間で up > down。**

2001–2020のup限定:

```text
trades       113
平均         +1.048%
中央値       +0.971%
勝率         61.9%
t            3.28
陽性年       16 / 20年
```

固定swapを除いてもup優位は維持されたため、
swap設定の副産物ではないと判断してfinal OOSへ進んだ。

### 2021–2025 FINAL OOS

事前固定条件:

```text
strategy
    sma / threshold=1
    sma_period=15
    counter_trade=false
    hold=20
    start=1
    long / short両方

regime
    AUD_JPY前営業日終値
    >=
    AUD_JPY前営業日200日SMA

configured baseline
    cost=0.005
    swap=+0.00891%/day

neutral carry
    configuredから固定swap寄与を除外

stress
    neutral carry - 0.5% / trade
```

program verdict:

```text
WEAK_PASS
```

ただし研究仮説として重要な `up > down` は失敗。

```text
AUD_JPY up
    trades             18
    neutral average    +0.134%
    neutral median     -0.287%
    neutral win rate   50.0%
    neutral t          +0.212
    stress average     -0.366%

AUD_JPY down
    trades             16
    neutral average    +0.750%

up - down
    average difference -0.616%
```

developmentで4/4期間続いたRegime差が、
final OOSで**逆転**した。

### 現在の正式評価

```text
Regime hypothesis
    FAIL

Trading strategy
    weak
    stressでマイナス

総合
    脱落
```

`up × short` はfinal OOS内では相対的に良かったが、
それは結果を見た後の情報なので採用しない。

同じ2021–2025を使って、

```text
up × shortだけ
SMA変更
hold変更
threshold変更
```

などへ変更してfinal OOSをやり直さない。

---

# 3. 原油まわりの有力仮説

## A-/B+ 5. GOLD → OIL は高ボラでも強い

OIL←GOLDではDirectionだけでなく、
Volatilityでも特徴がある。

平均の `high_vol - low_vol`:

```text
2001–2005    約 +0.04%
2006–2010    約 +2.61%
2011–2015    約 +1.10%
2016–2020   約 +10.89%
```

平均では **4/4期間で high_vol > low_vol**。

ただし2001–2005はほぼ差なしで、
中央値まで完全に揃うわけではない。

したがって現在は、

```text
OIL down
```

の方を強い仮説とする。

### 評価

A-/B+

補助的な特徴として記録。

---

## B+ 6. COPPER → OIL の予測関係

表記:

```text
OIL_USD ← COPPER_USD
```

2001–2015代表戦略は強かった。

```text
best IS t       約 2.90
代表Signal      smaなど
```

2016–2020の代表戦略:

```text
平均            約 +1.02%
中央値          約 +3.69%
勝率            約 58%
```

予測型として現在も有力候補。

### 重要

RegimeではGOLD→OILとは違う。

2016–2020ではむしろ、

```text
low_vol > high_vol
```

だった。

したがって、

> 原油Target戦略は全部同じ市場環境で強い

とは考えない。

Refごとにメカニズムが違う可能性が高い。

---

## 旧B+ → B 7. COPPER / OIL の2.5σ級大乖離後の短中期回帰

これは `OIL_USD ← COPPER_USD` の予測型とは別研究。

### Pair仮説

> COPPERとOILの相対価格が通常より極端に離れたときだけ、
> 20日前後でspread contractionが起きる可能性がある。

2001–2015 discovery:

```text
2.5σ → 20日edge     約 +3.564%
中央値              約 +4.065%
```

2016–2020 fixed hedgeの研究用edge:

```text
イベント数          12
20日edge平均        約 +5.219%
中央値              約 +9.048%
プラス率            約 58.3%
```

この `+5.219%` は固定20日後のspread contractionであり、
実際の売買P&Lそのものではない。

### 2016–2020 実売買化

固定条件:

```text
hedge       2001–2015固定
z lookback  60
entry       2.5σ、翌営業日終値
exit        zero cross翌日 / 最大20営業日
baseline    10bps/turnover + short 0.5bps/day
stress      20bps/turnover + short 1.0bps/day
```

結果:

```text
trades              12
gross average       +2.048%
baseline average    +1.808%
stress average      +1.568%
baseline win rate   75.0%
```

実売買化してもedgeが残ったため、
2021–2025 strategy-specific final OOSへ進んだ。

### 2021–2025 strategy-specific FINAL OOS

市場データ自体は別研究ですでに既知。
ただし、この2.5σ Pair戦略の損益としては未評価だった期間。

```text
program verdict
    WEAK_PASS

trades
    15

baseline
    average     +0.717%
    median      -0.798%
    win rate    46.7%
    t           +0.509
    terminal    +9.068%

stress
    average     +0.471%
    terminal    +5.126%
```

事前固定条件7項目のうち、

```text
baseline median > 0
baseline win rate >= 50%
```

だけ失敗。

一方、

```text
baseline平均
stress平均
baseline terminal
stress terminal
```

はすべてプラスだった。

年別baseline平均も5年中4年プラス。

ただしexit別:

```text
zero_cross
    2 trades
    average +7.694%

max_hold
    13 trades
    average -0.356%
```

で、少数の大勝ちへの依存が強い。

### 現在の正式評価

```text
研究評価
    B

実用
    見送り

状態
    edgeは完全には消えていない
    研究候補として残す
```

同じ2021–2025を使って、
zero-crossだけ・片方向だけ・entry_z変更・max_hold変更などの
救済最適化はしない。

---

## 旧B+ → 脱落 8. SILVER → OIL × OIL down

表記:

```text
OIL_USD ← SILVER_USD
```

固定代表戦略:

```text
signal          change
counter_trade   false
use_excess      false
threshold       1.0
hold_days       20
start_days      1
sma_period      100
```

2001–2020 developmentでは、

```text
2001–2005    down > up
2006–2010    down > up
2011–2015    down > up
2016–2020    down > up
```

が4/4期間で成立。

down全体:

```text
trades      116
average     +2.769%
median      +2.841%
win rate    62.9%
t           2.42
```

### 2021–2025 FINAL OOS

```text
program verdict
    FAIL

down
    trades      45
    average     -0.902%
    median      -0.446%
    win rate    44.4%
    t           -1.043
    stress avg  -1.402%

up
    trades      33
    average     +0.769%

down - up
    -1.670 pt
```

事前条件では取引数だけPASSし、
平均・中央値・勝率・stress・`down > up` はすべてFAIL。

### 結論

```text
Regime hypothesis
    FAIL

Trading strategy
    FAIL

総合
    脱落
```

final OOSで良かった `up × long` などを
同じ2021–2025で救済仮説へ変更しない。

また、

> OIL downなら他コモディティRefも一般的に強い

という一般則も支持が弱くなった。

OIL←GOLDでは相対的なdown優位だけ残ったが、
OIL←SILVERではRegime差そのものが逆転したため。

---

## B 9. NZD_USD → OIL_USD

過去の予測型探索では、

```text
OIL_USD ← NZD_USD
```

が複数回候補になった。

一部分析では2016年以降も比較的良い。

コモディティ通貨NZDと原油の
景気・リスク選好連動という経済的な筋もある。

ただしRegime Researchでは、

> OIL系全体で共通の高ボラ/低ボラ特性

は確認できなかった。

### 評価

B

予測型候補として残すが、
GOLD/COPPERより優先度は下。

---

# 4. EUR_GBPを情報源とする仮説

## 旧B+ → B 10. EUR_GBPは複数FXへ先行情報を持つ可能性

固定Target:

```text
GBP_USD
AUD_USD
AUD_JPY
NZD_USD
EUR_USD
```

各代表StrategyTaskは2001–2015だけで選抜済み。

### 4期間の横断性

```text
2001–2005    5/5平均プラス
             等Target平均 +0.417%

2006–2010    5/5平均プラス
             等Target平均 +1.204%

2011–2015    5/5平均プラス
             等Target平均 +0.389%

2016–2020    4/5平均プラス
             等Target平均 +0.136%
```

2016–2020:

```text
GBP_USD    +0.054%
AUD_USD    +0.204%
AUD_JPY    +0.498%
NZD_USD    -0.186%
EUR_USD    +0.108%
```

### 解釈

> EUR_GBPが複数FXへ横断情報を持つ

というテーマはdevelopmentでも完全には消えなかった。

ただし、

- 2016–2020の等Target平均は+0.136%まで弱化
- 5本中1本はマイナス
- GBP/AUD/NZD/EURの4 USDストレートは同じDI signal日程
- Target自体も相関するため、4つの独立edgeとは数えられない

### 現在の評価

```text
B
横断性は弱く残る
実用候補ではない
2021–2025確認を急がず保留
```

AUD_NZD source themeと同じ方法で比較してから
次の優先順位を決める。

---

## B 11. GBP_USD ← EUR_GBP

過去ランキングでは非常に強い。

- 多数の設定
- 複数Signal
- 高いIS t

で再現した。

しかし代表戦略の2016–2020は、

```text
平均 約 +0.054%
```

とかなり弱くなった。

### Regime

最初は low_vol で強く見えたが、
EUR_GBP系を広げると「低ボラ一般則」は崩れた。

### 評価

B

テーマとしては重要だが、
現在の最優先単独戦略ではない。

---

## B 12. AUD_USD ← EUR_GBP

2001–2015では強い。

```text
best IS t 約 3.08
```

2016–2020代表戦略:

```text
平均 約 +0.204%
```

GBP_USDよりは残ったが、
圧倒的ではない。

### 評価

B

EUR_GBPテーマの代表候補として残す。

---

## B 13. GOLD_USD ← EUR_GBP

Regime拡張研究で新しく目立った。

2016–2020:

```text
trades      約 61
平均        約 +1.005%
中央値      約 +0.994%
勝率        約 60.7%
t           約 2.27
```

ただし2001–2015の選抜時tは約1.50で、
元々の強い探索候補ではなかった。

### 評価

B

**新しい研究候補。**

OOSだけを見て本命へ昇格させない。

---

## B- 14. EUR_USD ← EUR_GBP

複数探索で候補として出る。

ただしAUD_JPYほど明確なRegime再現はない。

### 評価

B-

EUR_GBP横展開候補として記録。

---

## C 15. NZD_USD ← EUR_GBP

過去探索では候補になったが、
2016–2020の代表戦略は弱かった。

### 評価

C

優先度低下。

---

# 5. AUD_NZDを情報源とするクロス円仮説

## B+ 16. AUD_NZD → クロス円は研究テーマとして残る

主なTarget:

```text
EUR_JPY
CAD_JPY
CHF_JPY
GBP_JPY
```

AUD_NZDは豪州とNZの相対関係なので、
リスク選好・商品市場・金利差などを通じて
クロス円へ情報を持つ可能性がある。

2016–2020だけを見ると4銘柄すべて、

```text
down > up
```

だった。

しかし4期間に広げると完全再現ではなかった。

したがって、

> AUD_NZD系は全部downで強い

という一般則は採用しない。

---

## B 17. EUR_JPY ← AUD_NZD × EUR_JPY down

代表戦略の2016–2020:

```text
平均 約 +0.376%
t    約 1.41
```

Directionでは、

```text
2006–2010   down優位
2011–2015   down優位
2016–2020   down優位
```

2001–2005はほぼ同じ。

実質3期間でdown優位。

### 評価

B

AUD_NZDクロス円テーマの中では比較的有力。

---

## B 18. GBP_JPY ← AUD_NZD

2016–2020:

```text
平均    約 +0.670%
中央値  約 +0.292%
t       約 1.66
```

OOS全体では比較的良い。

ただしdown優位は4期間完全ではない。

### 評価

B

追加研究候補。

---

## B- 19. CHF_JPY ← AUD_NZD

2016–2020:

```text
平均 約 +0.295%
```

down優位は概ね3/4だが、
期間によって差が小さい。

### 評価

B-

---

## C 20. CAD_JPY ← AUD_NZD

過去は主要候補だったが、
2016–2020全体では、

```text
平均 約 -0.040%
```

となった。

Regimeで一部良いセルがあっても、
弱い元戦略を後付けフィルタで救済しない。

### 評価

C

優先度を下げる。

---

# 6. 株価指数・異種アセット系

## B- 21. USSPX500 → GBP_JPY

表記:

```text
GBP_JPY ← USSPX500_Futures
```

2001–2015代表:

```text
best t 約 2.81
bb / SMA200系
```

異種アセットで、
EUR_GBPやAUD_NZDとは情報源が違うため
分散候補として面白い。

ただし2016–2020代表戦略:

```text
平均    約 +0.173%
中央値  ほぼ 0
```

と弱い。

### 評価

B-

市場間関係としては面白いが優先度低下。

---

## B- 22. NQ100 ← USD_CHF

過去の候補分析では、

- USD_CHFを安全資産・リスク選好の代理として使う
- NQ100の反発を狙う逆張り型

という仮説が候補になった。

一部期間外成績も良かった。

ただし、現在の主要Regime検証の中心ではない。

### 評価

B-

追加検証候補。

---

## B- 23. GBP_JPY ← GBP_CHF

過去のStrategy Screeningで
複数指標・複数期間で候補になった。

### 評価

B-

現在の最上位テーマではないが、
EUR_GBP / AUD_NZD / OILとは異なるFX関係として記録。

---

# 7. SILVERを情報源とする候補

過去探索では次が候補になった。

```text
OIL_USD ← SILVER_USD
UK100_Futures ← SILVER_USD
US30_Futures ← SILVER_USD
```

この中では現在、

```text
OIL_USD ← SILVER_USD
```

が最も興味深い。

OIL down regimeでの再現もあるため、
他の2つより優先。

`UK100 ← SILVER`、`US30 ← SILVER` は
追加検証候補に留める。

---

# 8. 現在は弱い・追わない仮説

## 8.1 Pair: USD_CAD / OIL_USD

2001–2015では非常に強く見えた。

```text
ADF p             約 0.00075
cointegration p   約 0.0041
MR t              約 -4.82
2σ→20日edge       約 +0.726%
```

しかし2016–2020 fixed hedge:

```text
20日edge平均       約 -0.735%
中央値             約 -0.586%
プラス率           約 46.7%
```

### 結論

**脱落。**

重要な教材:

> 統計的に非常に強く見えるPairでも、
> 真のOOSで崩れる。

---

## 8.2 Pair: AUD_USD / OIL_USD

Discovery:

```text
2σ→20日 約 +0.749%
```

fixed OOS:

```text
約 -0.366%
```

### 結論

脱落。

---

## 8.3 Pair: NZD_USD / OIL_USD

Discovery:

```text
約 +0.835%
```

fixed OOS:

```text
約 -1.357%
```

### 結論

脱落。

注意:

これはPair平均回帰仮説の話。

```text
NZD_USD → OIL_USD
```

という予測型仮説とは別。

---

## 8.4 Pair: 中国電力 / 東北電力

fixed OOSで大きく悪化。

### 結論

脱落。

---

## 8.5 Pair: 中国電力 / 九州電力

fixed OOSでマイナス。

### 結論

脱落。

---

## 8.6 Pair: 関西電力 / 九州電力

fixed OOSでマイナス。

### 結論

脱落。

---

## 8.7 Pair: 関西電力 / 北海道電力

2001–2015では非常に良かったが、

```text
2016–2020 fixed OOS
20日edge 約 +0.011%
```

まで弱化。

### 結論

優先度大幅低下。

---

## 8.8 Pair: 中部電力 / 北海道電力

探索時は良かったが、
fixed OOSではマイナス。

### 結論

保留。

---

# 9. 否定された一般化

個別戦略が良いことと、
テーマ全体に同じ法則があることは別。

---

## 9.1 「EUR_GBP系は低ボラで強い」は採用しない

最初は、

```text
GBP_USD ← EUR_GBP
AUD_USD ← EUR_GBP
```

で low_vol が良く見えた。

しかしTargetを6本へ広げると、
高ボラ優位のものも出た。

### 結論

> EUR_GBPをRefにすれば低ボラで強い

という一般則はない。

Targetごとに見る。

---

## 9.2 「AUD_NZD → クロス円は全部downで強い」は採用しない

2016–2020では4本すべてdown優位だったが、
過去3区間を加えると完全には揃わない。

### 結論

テーマ全体へ一律downフィルタを入れない。

EUR_JPYなど個別に見る。

---

## 9.3 「OILをTargetにする戦略は高ボラで強い」は採用しない

2016–2020:

```text
GOLD   → OIL   high_vol型
COPPER → OIL   low_vol型
NZD    → OIL   ややlow_vol型
USD_CAD→ OIL   low_vol寄り
SILVER → OIL   high_vol型
```

### 結論

OIL Targetというだけでは共通Regimeにならない。

Refごとに別メカニズム。

---

# 10. VIX系

研究対象:

```text
NQ100 ← VIX
SPX500 ← VIX
```

2001–2015代表戦略のIS tが低い。

```text
NQ100 ← VIX    約 1.19
SPX500 ← VIX   約 0.72
```

2016–2020も強くない。

### 結論

C / 優先度低。

弱い元戦略をRegime条件で救済しない。

---

# 11. TRY_JPY系

TRY_JPYは過去ランキングで非常に強かった設定が多い。

しかし2021年以降に悪化した設定が多かった。

### 現在の位置づけ

主力候補ではない。

### 重要な教訓

> 長期間のインサンプルで非常に強くても、
> 市場構造が変わればedgeは崩れる。

structural break / regime change の教材。

---

# 12. 複数研究で同じ市場関係が出たもの

## 12.1 GOLD / OIL

### Predictive

```text
GOLD → OIL
```

が強い。

### Regime

```text
OIL down
```

で4/4期間強い。

high_volも平均では4/4優位。

### 意味

現在もっとも多面的に裏付けがある
予測型市場関係の1つ。

---

## 12.2 COPPER / OIL

### Predictive

```text
COPPER → OIL
```

が有力。

### Pair

2.5σ級の極端な乖離後に
20日前後のspread contraction。

### 意味

同じ2市場関係が、
**別の研究方法から2回浮上**した。

ただし同一戦略ではない。

---

## 12.3 EUR_GBP / FX

Strategy Screeningでは複数Targetへ広がる。

Regime ResearchではTargetごとに性質が違うことが分かった。

特に、

```text
EUR_GBP → AUD_JPY
+
AUD_JPY up
```

が強い。

---

## 12.4 AUD_NZD / クロス円

複数Targetで予測候補。

ただし一律Regimeは成立しない。

現在は、

```text
EUR_JPY ← AUD_NZD × EUR_JPY down
```

など個別仮説として扱う。

---

# 13. クラスターとして考えるべきもの

見かけ上は複数戦略でも、
同じ情報源・Target・市場テーマへ集中している。

## EUR_GBPクラスター

```text
EUR_GBP
↓
GBP_USD
AUD_USD
AUD_JPY
NZD_USD
EUR_USD
GOLD_USD
```

## AUD_NZDクラスター

```text
AUD_NZD
↓
EUR_JPY
CAD_JPY
CHF_JPY
GBP_JPY
```

## OIL Targetクラスター

```text
GOLD
COPPER
NZD_USD
USD_CAD
SILVER
↓
OIL
```

## 電力Pairクラスター

```text
中部 / 関西
中部 / 九州
```

当初は2本ともA+候補だったが、
2021–2025 FINAL OOSでは50/50 Portfolioが不合格。

```text
baseline terminal return   -3.811%
stress terminal return     -8.480%
```

現在は、

```text
中部 / 関西
    B-/C
    weak positive

中部 / 九州
    脱落
```

とする。

### 研究上の意味

このクラスターは現在の有力戦略ではなく、

- 共通銘柄を持つ複数edgeを独立と数えない
- developmentで強くてもfinal OOSで崩れる
- structural breakを疑う
- OOS後の救済最適化をしない

という教訓を残す研究例として扱う。

---

# 13.5 OIL_USD ← COPPER_USD final OOS

## 旧B+ → B- 予測型 OIL_USD ← COPPER_USD

2001–2015だけで選抜した代表戦略:

```text
signal          sma
threshold       1.0
sma_period      100
counter_trade   false
use_excess      false
hold_days       20
start_days      1
```

2001–2015:

```text
trades       206
average      +1.836%
median       +0.760%
win rate     53.4%
t            2.81
```

2016–2020 fixed development:

```text
trades       77
average      +1.016%
median       +3.691%
win rate     58.4%
```

方向別にはlongが強くshortが弱かったが、
final OOS前にlongだけへ変更せず**両方向のまま固定**した。

### 2021–2025 FINAL OOS

```text
program verdict
    WEAK_PASS

all
    trades       77
    average      +0.225%
    median       +0.115%
    win rate     50.6%
    t            +0.261
    stress avg   -0.275%

long
    trades       43
    average      +0.582%

short
    trades       34
    average      -0.226%
```

年別:

```text
2021    baseline +1.131%    stress +0.631%
2022    baseline +1.573%    stress +1.073%
2023    baseline -0.838%    stress -1.338%
2024    baseline -0.213%    stress -0.713%
2025    baseline -0.488%    stress -0.988%
```

### 現在の正式評価

```text
edge
    わずかに残った

robustness
    stressでマイナス
    2023–2025は3年連続で平均マイナス

総合
    B-
    実用戦略としては見送り
```

2021–2025を見た後でlongだけ、SMA変更、threshold変更、
hold変更、期間除外などを行い、同じ期間をfinal OOSとしてやり直さない。

---

# 14. 現時点の総合研究順位

現在は新規候補の順位付けを一旦停止する。

```text
final OOS監査対象          6
deployable                 0
final baseline平均プラス  4/6
final stress平均プラス    1/6
Regime優位方向維持        1/3
```

主な失敗型:

1. edge compression
   - OIL←COPPER

2. absolute edge collapse
   - OIL←GOLD × down

3. regime inversion
   - AUD_JPY←EUR_GBP × up
   - OIL←SILVER × down

4. portfolio / cost fragility
   - utility 50/50 Pair

5. rare-event dependence
   - COPPER/OIL 2.5σ Pair

残すもの:

```text
COPPER/OIL 2.5σ Pair
    B / paper-forward候補

EUR_GBP → 複数FX
    B / development-only / 保留

AUD_NZD → クロス円
    未完了 / 凍結
```

ここからは
「どの候補が一番良いか」より
「どう選べばOOSで残りやすいか」を優先する。

---

# 15. 次に検証する順番

## 最優先: Parameter Plateau Research

仮説:

> best t-value 1点の高さより、
> 近傍パラメータの広い安定性の方が
> developmentで残りやすい。

検証期間:

```text
2001–2015
    selection / plateau測定

2016–2020
    development

2021–2025
    新しいplateau指標の学習に使わない
```

候補指標:

```text
best_t
neighbor_mean_t
neighbor_worst_t
neighbor_positive_ratio
signal_type_support
positive_year_ratio
```

まず単独指標として観察する。
final OOS数件に合わせた複雑な複合スコアは作らない。

---

## 未完了テーマ

```text
AUD_NZD → クロス円
EUR_GBP → 複数FXの追加検証
```

は凍結。

method auditが終わるまで
追加のfinal OOSを消費しない。

---

# 16. 今後の別研究候補

1. **Parameter plateau / neighborhood robustness**
   - 最良一点だけでなく近傍パラメータでも残るか

2. **Permutation / randomization test**
   - block shift / circular shiftなどで偶然のedgeか確認

3. **Lead-lag decay**
   - 1日先だけでなく何日まで情報が残るか

4. **Structural break**
   - 市場関係がいつ変化したか
   - 中部/関西・中部/九州は重要な教材
   - ただし2021–2025を使った救済最適化とは分ける

5. **Strategy return correlation / clustering**
   - 戦略本数ではなく独立edge数を評価

6. **Cross-sectional strategy**
   - 単独target/refとは違う横断型研究

---

# 17. 新しいチャットで最初に理解すること

1. 新規候補探索は一旦停止した。
2. final OOSまで到達した監査対象は6仮説。
3. 本番投入可と判断した案は0。
4. final baseline平均プラスは4/6。
5. final stress平均プラスは1/6。
6. Regime仮説3本中、優位方向維持は1本。
7. AUD_JPY×upとOIL←SILVER×downはfinalでRegime差が逆転。
8. OIL←GOLD×downは相対差のみ残り絶対edgeは消えた。
9. OIL←COPPERはdevelopmentからfinalへ大幅縮小しstressでマイナス。
10. utility Pair portfolioはfinal FAIL。
11. COPPER/OIL 2.5σ Pairだけstress後もプラスだがrare-event依存が強い。
12. EUR_GBP source themeはB・保留。
13. AUD_NZD source themeは未完了・凍結。
14. 次はParameter Plateau Research。
15. 2021–2025 final結果を新スコア最適化に使わない。
16. 2001–2015でplateauを測り、2016–2020だけで検証する。

---

# 18. 再開地点

> **新規候補探索を止め、研究方法の監査へ移行。次はbest t-value 1点ではなく、周辺パラメータの広い安定性（Parameter Plateau）が2016–2020で残りやすいかを調べる。**

まず2001–2015だけからplateau指標を計算し、
2016–2020との関係を見る。

2021–2025 final OOSは
新しいplateauスコアの学習には使わない。
