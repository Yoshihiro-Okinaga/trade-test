# Research Method Audit — Step 1

## 結論

- final OOS監査対象: **6**
- deployable: **0**
- final baseline平均プラス: **4/6**
- final stress平均プラス: **1/6**
- Regime優位方向維持: **1/3**
- development→final平均残存率の中央値: **9.0%**

この残存率はstudy familyが混在するため記述統計に留め、
新しい選抜式の最適化には使わない。

## Final OOS監査

| Candidate | Family | Dev avg | Final avg | Stress avg | Retention | Verdict |
|---|---|---:|---:|---:|---:|---|
| Utility 50/50 Pair Portfolio | pair | +0.201% | -0.086% | -0.206% | -42.9% | FAIL |
| OIL_USD <- COPPER_USD | predictive | +1.016% | +0.225% | -0.275% | 22.1% | B- / skip |
| OIL_USD <- GOLD_USD x OIL down | regime | +5.155% | +0.029% | -0.471% | 0.6% | B- / regime-only survival |
| AUD_JPY <- EUR_GBP x AUD_JPY up | regime | +0.766% | +0.134% | -0.366% | 17.5% | FAIL |
| OIL_USD <- SILVER_USD x OIL down | regime | +0.867% | -0.902% | -1.402% | -103.9% | FAIL |
| COPPER_USD / OIL_USD 2.5sigma Pair | pair | +1.808% | +0.717% | +0.471% | 39.7% | B / observe |

## 失敗の型

1. **edge compression** — OIL←COPPER
2. **absolute edge collapse** — OIL←GOLD × down
3. **regime inversion** — AUD_JPY×up / OIL←SILVER×down
4. **portfolio / cost fragility** — utility 50/50 Pair
5. **rare-event dependence** — COPPER/OIL 2.5σ Pair

## 次のStep

新しい候補を増やさず、**Parameter Plateau Research**へ進む。

2001–2015だけで、

- best t-value
- 近傍パラメータ平均
- 近傍パラメータ最悪値
- 近傍のプラス率
- Signal typeをまたいだ再現数
- 5年区間の陽性率

を測り、2016–2020 developmentとの関係を見る。
2021–2025 final OOSは新しいplateauスコアの学習には使わない。