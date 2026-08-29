# RESEARCH_HYPOTHESES

最終更新: **2026-08-29**

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

特に、

- インサンプル
- 2016–2020のOOS
- 2021年以降
- Pairの研究edge
- 実際の売買P&L

は別物です。

---

# 1. 現時点の最重要仮説

## A+ 1. 中部電力 / 関西電力の短中期relative-value回帰

### 仮説

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

### なぜ重要か

探索期間で強かっただけでなく、
**未知期間の価格でhedge ratioを再推定しなくても残った**。

現在のPair Researchで最も強い候補。

### 注意

2016–2020を見た後で候補選定しているため、
2016–2020は今後 development data と考える。

**2021年以降はまだ見ない。**

---

## A+ 2. 中部電力 / 九州電力の短中期relative-value回帰

### 仮説

> 中部電力と九州電力も、
> 大きな相対価格乖離後に20日前後で縮小しやすい。

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

### 評価

中部/関西と並ぶPair本命。

### 最大の注意

この2つは、

```text
中部 / 関西
中部 / 九州
```

の両方に中部電力が入る。

したがって、

> 独立した2個のedge

ではなく、

> **中部電力を中心とする1つのrelative-valueテーマ**

かもしれない。

将来のポートフォリオでは完全な分散と数えない。

---

## A+ 3. GOLD_USD → OIL_USD は、OILが長期下降局面で特に強い

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

IS trades       192
IS average      約 +2.057% / trade
IS t            約 2.98
```

2016–2020:

```text
OOS trades      67
平均            約 +2.094%
中央値          約 +4.610%
勝率            約 59.7%
```

元戦略自体がかなり強い。

### Regime仮説

TargetであるOILが、

```text
前営業日終値 < 前営業日200日SMA
```

の **down regime** のとき、
GOLD → OIL戦略が特に強い。

4期間の `down - up` 平均差:

```text
2001–2005   約 +5.24%
2006–2010   約 +6.87%
2011–2015   約 +1.88%
2016–2020   約 +5.70%
```

**4/4期間で down > up。**

2016–2020:

```text
OIL down
平均        約 +5.15%
中央値      約 +5.88%

OIL up
平均        約 -0.54%
中央値      約 -0.36%
```

long / shortに分けてもdown優位が残った。

### 現在の解釈

単に、

> OIL下落局面だからショートが儲かった

だけでは説明しにくい。

現在のRegime Researchで最重要の仮説。

### 将来の使い方

本体へRegimeを統合する場合の第一候補:

```text
GOLD → OIL のシグナル
+
OILが200日SMAより下
```

ただし、まだ本体へ組み込まない。

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

OIL←GOLD × down に次ぐ、
非常にきれいなRegime仮説。

将来の固定フィルタ候補:

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

### ポートフォリオでの意味

戦略数ではなく、

> **独立したリスクテーマ数**

で見る必要がある。

---

# 14. 現時点の総合研究順位

## A+

1. **中部電力 / 関西電力**
2. **中部電力 / 九州電力**
3. **OIL_USD ← GOLD_USD × OIL down**

## A

4. **AUD_JPY ← EUR_GBP × AUD_JPY up**

## B+

5. **OIL_USD ← GOLD_USD × high_vol**
6. **OIL_USD ← COPPER_USD**
7. **COPPER_USD / OIL_USD の2.5σ大乖離**
8. **OIL_USD ← SILVER_USD × OIL down**
9. **EUR_GBP → 複数FXという情報源テーマ**
10. **AUD_NZD → クロス円という情報源テーマ**

## B

11. **EUR_JPY ← AUD_NZD × EUR_JPY down**
12. **GBP_JPY ← AUD_NZD**
13. **GBP_USD ← EUR_GBP**
14. **AUD_USD ← EUR_GBP**
15. **GOLD_USD ← EUR_GBP**
16. **OIL_USD ← NZD_USD**

## B- / 追加検証

17. **CHF_JPY ← AUD_NZD**
18. **EUR_USD ← EUR_GBP**
19. **GBP_JPY ← USSPX500_Futures**
20. **NQ100_Futures ← USD_CHF**
21. **GBP_JPY ← GBP_CHF**
22. **UK100_Futures ← SILVER_USD**
23. **US30_Futures ← SILVER_USD**
24. **AUD_JPY ← GBP_CHF**
25. **USD_JPY ← USSPX500_Futures**

## C / 優先度低

- CAD_JPY ← AUD_NZD
- NZD_USD ← EUR_GBP
- GBP_JPY ← UK100_Futures
- VIX → NQ100
- VIX → SPX500
- TRY_JPY系

---

# 15. 次に検証する順番

## 最優先

Pair本命2組:

```text
中部 / 関西
中部 / 九州
```

について売買ルール固定。

**2021年以降を見ない。**

---

## Pairルール固定後

2021+を最終OOSとして一度だけ評価。

合格したら、

```text
backtest統合
↓
Walk-forward
↓
コスト耐性
↓
ポートフォリオ
```

へ進む。

---

## Regime Research

現状はいったん一区切り。

将来、本体へ固定フィルタとして導入する候補:

```text
第1候補:
OIL ← GOLD
+
OIL down

第2候補:
AUD_JPY ← EUR_GBP
+
AUD_JPY up
```

Regimeの20 / 252 / 200は
今回の結果を見て変更しない。

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

5. **Strategy return correlation / clustering**
   - 戦略本数ではなく独立edge数を評価

6. **Cross-sectional strategy**
   - 単独target/refとは違う横断型研究

---

# 17. 新しいチャットで最初に理解すること

1. 予測型とPair Researchは別現象。
2. Regime Researchは予測型戦略の市場環境依存を見る研究。
3. Pair本命は中部/関西と中部/九州。
4. この2本は中部電力を共有するため完全独立ではない。
5. Pairの2021+はまだ最終ホールドアウト。
6. OIL←GOLD × OIL down が現在最強のRegime仮説。
7. AUD_JPY←EUR_GBP × up も4期間再現。
8. EUR_GBP系=low_volという一般化は棄却。
9. AUD_NZD系=downという一般化も一律には採用しない。
10. OIL Target戦略もRefごとにRegimeが異なる。
11. COPPER/OILは予測型と2.5σPairの両方で面白いが別戦略。
12. 弱い戦略を後付けRegimeで救済しない。
13. 研究結果を見た後の細かいパラメータ調整を避ける。
14. 次にやるのはPair本命2組の単純売買ルール固定。

---

# 18. 再開地点

> **中部電力/関西電力と中部電力/九州電力について、2021年以降を見ずに単純なPair売買ルールを固定する。**

Regimeを再開するときは、

> **OIL←GOLD × OIL down と AUD_JPY←EUR_GBP × AUD_JPY up を、固定条件として本体へ統合する価値があるか検討する。**

から始める。
