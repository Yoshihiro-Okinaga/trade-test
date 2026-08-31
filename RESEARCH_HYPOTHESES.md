# RESEARCH_HYPOTHESES

最終整理: **2026-08-31**

このファイルは、研究を再開するときに必要な**結論だけ**を残します。
詳細CSVは保存せず、必要ならPythonから再生成します。

---

## 1. 現在の研究判断

```text
本番投入可能     なし
新規研究         停止中
次の研究         Parameter Plateau条件で未消費候補を整理
```

final OOSまで進めた研究では、IS/developmentで見えたedgeがfinalで
大きく縮む例が多く、従来の「best t-value 1本選抜」だけでは不十分でした。

過去監査の要点:

```text
final OOS監査対象          6
本番投入可                 0
final baseline平均プラス  4/6
final stress平均プラス    1/6
Regime優位方向維持        1/3
```

---

## 2. 現在のbase strategy仮説

Parameter Plateau研究から、暫定的に次を使います。

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

> best tが高いだけでなく、直近のparameter設定も最低限強いstrategyを残す。

既にfinal OOSを消費した4戦略での監査では、Rule Bは
生存扱い2/2を残し、FAIL 2件中1件を事前に落としました。
ただしサンプルは小さく、成功を証明するものではありません。

Regime / direction / volatility filterはParameter Plateauでは検証できません。
追加する場合は独立した仮説としてdevelopment → finalをやり直します。

---

## 3. 残している市場仮説

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
Parameter Plateauの共通プロトコルを優先する。

### OIL ← GOLD × OIL down — B- / 特徴量候補

final 2021–2025でも `down > up` の相対差は残ったが、
down自体のbaseline平均はほぼ0、stressではマイナス。
**売買戦略としては見送り。Regime特徴としてのみ記録。**

---

## 4. 見送り・脱落

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

## 5. Holdoutの扱い

- 2021–2025は複数研究ですでに部分的に見ている。
- OIL関連、AUD_JPY関連などは市場データとしてpristineとは呼ばない。
- 未消費候補でも「strategy-specific outcomeが未確認」かを区別する。
- finalを見た後のlong-only、方向変更、SMA変更、threshold変更などは採用しない。
- 2026以降をforward扱いする場合も、そのデータを既に見ていないか確認する。

---

## 6. 再開時の最初の作業

1. READMEの手順でIS / developmentランキングを再生成。
2. `research/parameter_plateau.py` を実行。
3. `parameter_plateau_candidates.csv` を作る。
4. 2021–2025 strategy-specific outcomeが未消費の候補を識別。
5. 経済的説明・重複・Ref依存を確認して**1本だけ**選ぶ。
6. final条件を固定してから次へ進む。

研究を再開するまでは、新しい仮説を追加しない。
