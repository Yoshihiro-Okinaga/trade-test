# RESEARCH_HYPOTHESES

最終整理: **2026-09-13**

このファイルには、現在残している候補と重要な結論だけを記録します。
詳細CSVは必要なら再生成します。

## 1. 現在地

```text
本番投入可能: なし
基本方針: IS → 固定 → Development → 固定 → Final OOS / Walk-forward
OOSを見た後の救済調整: しない
```

特に2021–2025は複数研究ですでに使用しています。
この期間を見た後の `long-only`、signal除外、hold / SMA / threshold変更は新しい仮説として扱います。

---

## 2. 現在の有望候補

### A. AUD_USD <- GBP_CHF / counter — B / Forward観察

Signal Consensus研究ラウンド1で唯一Final OOSまでPASSした候補。
条件は固定済み。

```text
BB      counter  threshold=1.0   hold=1  start=1  sma=50
Change  counter  threshold=1.0   hold=1  start=1  sma=10
RSI     counter  threshold=20.0  hold=1  start=1  sma=10
SMA     counter  threshold=1.0   hold=1  start=1  sma=15
Stoch   counter  threshold=30.0  hold=1  start=1  sma=15
Streak  counter  threshold=2.5   hold=5  start=1  sma=10
```

結果:

```text
2001–2015 IS panel平均          約 +0.0767%
2016–2020 Development panel平均 +0.0421%  PASS
2021–2025 Final OOS panel平均    +0.0244%  PASS
```

edgeは縮小しているためproduction-readyではない。
**条件を変えずForward観察。**

---

### B. 6752_パナソニック <- USD_JPY — 研究継続

現在もっとも明確な株式候補。

固定StrategyTask:

```text
signal_type       = breakout
counter_trade     = false   # trend
threshold_width   = 0.5
hold_days         = 2
start_days        = 1
sma_period        = 10
use_excess_return = false
no_overlap        = true
```

Walk-forwardで同じTaskが2018–2020の3年連続で選ばれ、3/3年プラス。

```text
2018–2020: 247 trades
平均       +0.1660% / trade
合計       +41.01 percentage points
```

その後、parameterを固定して2021–2025まで評価:

```text
2021–2025: 431 trades
平均       +0.0926% / trade
合計       +39.89 percentage points
t値        約 +0.67
プラス年   2 / 5
```

Long側だけを見ると良かったが、これはOOSを見た後の情報なので **long-onlyへ変更しない**。
また株式costが現在0のため、次に確認するのはparameter変更ではなく **コスト耐性**。

---

### C. 9504_中国電力 <- AUD_NZD / counter — 研究継続

Pair単位Walk-forwardで2016–2020の5フォールドすべて選抜。
5回すべて `counter_trade=true` だった。

```text
2016–2020: 161 trades
平均       +0.1471% / trade
合計       +23.68 percentage points
t値        約 +0.94
プラス年   3 / 5
```

選ばれたsignalはDI / BBで変化したが、**AUD_NZD → 中国電力の逆張り方向は一貫**。
個別parameterより「Pair + counter方向」の仮説として残す。

---

### D. 9504_中国電力 <- AUD_USD / counter — 保留

2016・2017の2フォールドだけ品質条件を通過。
両方で同じTaskが選ばれた。

```text
signal_type     = di
counter_trade   = true
threshold_width = 20
hold_days       = 10
start_days      = 1
sma_period      = 20
```

```text
12 trades
平均  +1.1838% / trade
合計  +14.21 percentage points
2 / 2フォールドでプラス
```

数字は良いが **12 tradesしかないため判断しない**。

---

### E. COPPER / OIL 2.5σ extreme Pair — B / Forward観察

- 2001–2015で大乖離後、20日前後の収束傾向。
- 2016–2020も固定ルールでプラス。
- 2021–2025もstress後プラス。
- Finalは15 closed tradesと少なく、少数の大勝ちへの依存が強い。

**実運用は見送り。条件固定でForward観察。**

---

### F. EUR_GBP -> 複数FX — B / 保留

Target:

```text
GBP_USD
AUD_USD
AUD_JPY
NZD_USD
EUR_USD
```

2016–2020 Development:

```text
平均プラスTarget  4 / 5
equal-target平均  +0.136%
worst Target       -0.186%
```

2001–2015からedgeは大きく減衰。
特に `AUD_USD <- EUR_GBP` は複数signalで同方向に現れたが、独立edgeが複数あるとは数えない。
**B / 保留。**

---

### G. AUD_NZD -> JPY crosses — 未完了 / 凍結

候補Target:

```text
EUR_JPY
CAD_JPY
CHF_JPY
GBP_JPY
```

旧研究は途中で停止。
再開する場合は旧条件をそのまま続けず、新しい共通手順で事前定義してから行う。

---

### H. OIL <- GOLD × OIL down — B- / 特徴量候補

2021–2025でも `down > up` の相対差は残ったが、down側baseline平均はほぼ0でstressはマイナス。
**売買戦略としては見送り。Regime特徴としてのみ残す。**

---

## 3. 明確に優先度を下げた組み合わせ

再調整して救済しない。

```text
5401_日本製鉄 <- CAD_JPY            Walk-forward 2016–2020: 0/5年プラス、合計 -86.29pt
6752_パナソニック <- CHF_JPY        Walk-forward: 0/3年プラス
6752_パナソニック <- EUR_JPY        Walk-forward: 1/5年プラス
EUR_CHF <- NZD_USD / counter         Development REJECT
US30_Futures <- EUR_NZD / trend      Development REJECT
GBP_USD <- EUR_JPY / trend           Development REJECT
GBP_CHF <- NZD_USD / counter         Development REJECT
CAD_JPY <- GBP_CHF / counter         Development REJECT
OIL <- COPPER predictive             Finalでedge縮小、stress negative
OIL <- SILVER × OIL down             FAIL
AUD_JPY <- EUR_GBP × AUD_JPY up      Regime FAIL
Utility Pair portfolio               FAIL
```

---

## 4. 今後の優先順位

1. `6752_パナソニック <- USD_JPY / breakout` のコスト耐性を確認する。
2. `9504_中国電力 <- AUD_NZD / counter` をparameter最適化ではなくPair仮説として検証する。
3. `9504_中国電力 <- AUD_USD / counter` はサンプル不足のため追加データ待ち。
4. `AUD_USD <- GBP_CHF / counter` と `COPPER / OIL` は条件固定でForward観察する。
5. OOS済み候補を過去期間へ合わせて再調整しない。
