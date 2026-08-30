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

## A 4. EUR_GBP → AUD_JPY は、AUD_JPY上昇局面で強い

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

IS trades       約 172
IS average      約 +0.909%
IS t            約 2.72
```

2016–2020:

```text
trades          約 60
平均            約 +0.498%
中央値          約 +0.545%
勝率            約 58.3%
```

### Regime仮説

AUD_JPYが、

```text
前営業日終値 >= 200日SMA
```

の **up regime** で強い。

`down - up` 平均差:

```text
2001–2005   約 -0.75%
2006–2010   約 -0.86%
2011–2015   約 -1.15%
2016–2020   約 -0.42%
```

すべてマイナス。

つまり、

**4/4期間で up > down。**

### 現在の評価

**現在の最優先Regime仮説。**

OIL←GOLD × down はfinal OOSでRegime差こそ再現したが、
絶対edgeはほぼ消え、stressではマイナスだった。

そのため次はこのAUD_JPY仮説を、
同じ厳格な手順で検証する。

固定フィルタ候補:

```text
EUR_GBP → AUD_JPY
+
AUD_JPYが200日SMAより上
```

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

## B+ 7. COPPER / OIL の2.5σ級大乖離後の短中期回帰

これは上の「COPPER → OIL予測」とは別研究。

### Pair仮説

> COPPERとOILの相対価格が通常より極端に離れたときだけ、
> 20日前後でspread contractionが起きる可能性がある。

2001–2015:

```text
2.5σ → 20日edge     約 +3.564%
中央値              約 +4.065%
```

2016–2020 fixed hedge:

```text
イベント数          12
20日edge平均        約 +5.219%
中央値              約 +9.048%
プラス率            約 58.3%
```

### 注意

- イベント数が少ない
- 40日では悪化
- 強い長期cointegrationではない

したがって、

> 長期均衡へ戻るPair

ではなく、

> **極端な乖離後だけ起きる20日前後の反応**

という別仮説。

---

## B+ 8. SILVER → OIL はOIL下降局面で強い可能性

表記:

```text
OIL_USD ← SILVER_USD
```

2016–2020の予測戦略はプラス。

さらに平均では、

```text
down > up
```

が4/4期間で成立。

ただし、

- 元戦略の強さ
- 中央値の一貫性

はOIL←GOLDより弱い。

### 評価

B+

OIL←GOLDの「別Refでの部分的再現」として興味深い。

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

## B+ 10. EUR_GBPは複数FXへ先行情報を持つ可能性

過去のStrategy Screeningでは、

```text
GBP_USD ← EUR_GBP
AUD_USD ← EUR_GBP
AUD_JPY ← EUR_GBP
NZD_USD ← EUR_GBP
EUR_USD ← EUR_GBP
```

などが何度も候補になった。

特に2001–2015では、

```text
GBP_USD ← EUR_GBP   best t 約 3.11
AUD_USD ← EUR_GBP   best t 約 3.08
AUD_JPY ← EUR_GBP   best t 約 2.72
```

と強い。

### 現在の解釈

> EUR_GBPが複数FXに情報を持つ

というテーマ自体は残る。

ただしTargetごとに性質が違う。

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

# 14. 現時点の総合研究順位

PairとOIL←GOLDのfinal OOSを反映した**現在順位**。

## A / 最優先

1. **AUD_JPY ← EUR_GBP × AUD_JPY up**

## B+

2. **OIL_USD ← GOLD_USD × high_vol**
3. **OIL_USD ← COPPER_USD**
4. **COPPER_USD / OIL_USD の2.5σ大乖離**
5. **OIL_USD ← SILVER_USD × OIL down**
6. **EUR_GBP → 複数FXという情報源テーマ**
7. **AUD_NZD → クロス円という情報源テーマ**

## B

8. **EUR_JPY ← AUD_NZD × EUR_JPY down**
9. **GBP_JPY ← AUD_NZD**
10. **GBP_USD ← EUR_GBP**
11. **AUD_USD ← EUR_GBP**
12. **GOLD_USD ← EUR_GBP**
13. **OIL_USD ← NZD_USD**

## B- / 現象は残ったが主力見送り

- **OIL_USD ← GOLD_USD × OIL down**
  - 2021–2025で `down > up` は再現
  - down baseline平均 +0.029%
  - stress平均 -0.471%
  - Regime現象は合格、売買戦略としては見送り

## B- / 追加検証

14. **CHF_JPY ← AUD_NZD**
15. **EUR_USD ← EUR_GBP**
16. **GBP_JPY ← USSPX500_Futures**
17. **NQ100_Futures ← USD_CHF**
18. **GBP_JPY ← GBP_CHF**
19. **UK100_Futures ← SILVER_USD**
20. **US30_Futures ← SILVER_USD**
21. **AUD_JPY ← GBP_CHF**
22. **USD_JPY ← USSPX500_Futures**

## B-/C / 観察

- **中部電力 / 関西電力**
  - final OOS baselineは弱くプラス
  - stressではマイナス
  - 主力候補から降格

## C / 優先度低

- CAD_JPY ← AUD_NZD
- NZD_USD ← EUR_GBP
- GBP_JPY ← UK100_Futures
- VIX → NQ100
- VIX → SPX500
- TRY_JPY系

## 脱落

- **中部電力 / 九州電力**
  - 2021–2025 final OOSでgrossからマイナス
- **中部/関西 + 中部/九州 50/50 Pair Portfolio**
  - baseline terminal return -3.811%

---

# 15. 次に検証する順番

## 最優先

```text
AUD_JPY ← EUR_GBP
+
AUD_JPY up
```

固定Regime定義:

```text
前営業日のAUD_JPY終値
>=
前営業日のAUD_JPY 200日SMA
```

2001–2015で固定された代表戦略:

```text
signal          sma
threshold       1
sma_period      15
counter_trade   false
use_excess_return false
hold_days       20
start_days      1
```

この仮説は、

```text
2001–2005
2006–2010
2011–2015
2016–2020
```

の4期間すべてで `up > down` が確認されている。

次にやること:

```text
既存戦略を固定
↓
2001–2020で実トレード単位のRegime差を再確認
↓
合否基準・コスト耐性を2021+を見る前に固定
↓
2021–2025 FINAL OOSを一度だけ
```

変更しないもの:

```text
direction SMA     200日
signal SMA        15日
threshold         1
hold              20営業日
start             1営業日
counter_trade     false
```

---

## OIL_USD ← GOLD_USD × OIL down

2021–2025 final OOSまで完了。

```text
verdict
    WEAK_PASS

Regime
    down > up は再現

絶対edge
    down baseline平均 +0.029%
    down stress平均   -0.471%
```

現在はB-。

同じ2021–2025を使って、

```text
SMA変更
hold変更
threshold変更
short除外
down強度フィルタ追加
```

などを行い、final OOSとしてやり直さない。

---

## Pair Research

中部/関西・中部/九州を使った現在のPair本命研究は終了。

2021–2025はすでにfinal OOSとして開封済み。

今後この期間を見て、

```text
entry threshold
z lookback
max hold
片方向化
Pair選択
allocation
```

を変更した場合、
それは**新しいdevelopment研究**として扱う。

同じ2021–2025を再びfinal OOSとは呼ばない。

2026年はPair final OOSで未使用。

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

1. 予測型とPair Researchは別現象。
2. Regime Researchは予測型戦略の市場環境依存を見る研究。
3. Pair 50/50 Portfolioは2021–2025 final OOSで正式に不合格。
4. 中部/九州はPair候補から脱落。
5. 中部/関西はweak positiveだがB-/Cへ降格。
6. OIL←GOLD × OIL down は2021–2025 final OOSまで完了。
7. OIL←GOLDは `down > up` のRegime差自体はfinal OOSでも再現。
8. ただしdown baseline平均は+0.029%、stress平均は-0.471%。
9. OIL←GOLD × down は現在B-で、実用戦略としては見送り。
10. OIL←GOLDの2021–2025を条件変更してfinal OOSとしてやり直さない。
11. **AUD_JPY←EUR_GBP × AUD_JPY up が現在の最優先仮説。**
12. EUR_GBP系=low_volという一般化は棄却。
13. AUD_NZD系=downという一般化も一律には採用しない。
14. OIL Target戦略もRefごとにRegimeが異なる。
15. COPPER/OILは予測型と2.5σPairの両方で面白いが別戦略。
16. 弱い元戦略を後付けRegimeで救済しない。
17. 研究結果を見た後の細かいパラメータ調整を避ける。
18. 次にやるのはAUD_JPY←EUR_GBP × AUD_JPY upの実トレード再確認。

---

# 18. 再開地点

> **Pairはfinal OOS不合格。OIL←GOLD × OIL down はRegime差のみ再現し、売買戦略としては見送り。次は `AUD_JPY ← EUR_GBP × AUD_JPY up` を、既存の200日SMAレジーム定義を変えずに検証する。**

まず、

```text
2001–2020
```

だけを使って、
既存の固定戦略について `up / down` の実トレード差を再確認する。

その結果が既存Regime研究と一致すれば、
2021–2025を開ける前に合否基準とコスト耐性を固定する。
