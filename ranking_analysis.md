# Ranking Analysis

通常ランキング `trade_ranking.csv` を、人間が後から判断材料として読み返すための分析メモです。

このファイルは **ランキング上位をそのまま採用するための答えではありません**。
ランキング内での強さ、時系列での残存、複数設定での再現性を分けて記録します。

最終更新: 2026-08-22

## 1. 今回の分析データ

対象ファイル:

```text
trade_ranking.csv
```

今回読み込んだ内容:

- 行数: 10,000
- 列数: 34
- Target: 30 種類
- Ref: 30 種類
- Signal: bb, change, di, sma, stoch
- `use_excess_return`: false のみ
- `hold_days`: 20
- `start_days`: 1
- `sma_period`: 10 / 15 / 50 / 100 / 200

`trade_ranking.csv` は `main.py` が `t_value` 降順で出力した上位10,000行です。
全タスクが10,000件を超える場合、全件は `trade_ranking_full.csv` 側にあります。

### ranking_period について

CSV自体には生成時の `ranking_period` が書かれていません。
現行プロジェクトの `config.toml` は `ranking_period = [2008, 2020]` なので、
**今回もその設定で生成したものとして分析**しています。

この前提なら、`t_value` / `average_pct` / `trade_count` など順位付けの統計は
2008-2020年で計算され、`average_pct_2021_` はその後の期間を見る重要な列です。
生成時の設定が違う場合、この解釈だけは読み替えてください。

## 2. まず結論

今回の結果から最も重要なのは次の4点です。

1. **ランキング最上位と2021年以降の強さは一致していない。**
2. **TRY_JPY 系はインサンプル上位を大量に占めるが、2021年以降に崩れた設定が多い。**
3. **過去から候補にしていた EUR_GBP 系、原油系、AUD_NZD 系の一部は現在も複数設定で残っている。**
4. **1設定だけの最高順位より、同一ペアが複数シグナル・複数パラメータで再現することを重視すべき。**

上位10設定のうち、2021年以降も平均損益がプラスなのは **2/10** だけです。
上位100では **54/100** がプラスです。

上位100に限ると、インサンプルの `t_value` と `average_pct_2021_` の相関は
**-0.129** でした。10,000行全体でも **0.021** です。
少なくとも今回の候補集合では、`t_value` が高いほど2021年以降も強い、という単純な関係は見えません。

また上位100のうち、5つの期間列
`2001-2005 / 2006-2010 / 2011-2015 / 2016-2020 / 2021+` がすべてプラスなのは
**39設定**でした。

## 3. 現在のランキング Top 10

| Rank | Pair | Signal | Counter | SMA | Width | Trades | Win % | Avg % | t | 2021+ Avg % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | TRY_JPY ← GOLD_USD | sma | false | 200 | 1 | 197 | 60.4 | +1.213 | 3.292 | -0.405 |
| 2 | AUD_JPY ← EUR_AUD | bb | false | 15 | 2 | 157 | 59.9 | +0.970 | 3.280 | -0.145 |
| 3 | TRY_JPY ← NQ100_Futures | stoch | false | 50 | 30 | 174 | 59.2 | +1.310 | 3.261 | -0.500 |
| 4 | NZD_JPY ← EUR_AUD | bb | false | 15 | 2 | 157 | 57.3 | +1.021 | 3.249 | -0.263 |
| 5 | TRY_JPY ← NQ100_Futures | bb | false | 15 | 1.5 | 221 | 57.0 | +1.164 | 3.176 | -0.720 |
| 6 | TRY_JPY ← GOLD_USD | change | false | 200 | 1 | 199 | 62.8 | +1.158 | 3.150 | -0.078 |
| 7 | TRY_JPY ← NQ100_Futures | bb | false | 50 | 1 | 186 | 58.1 | +1.183 | 3.145 | -0.299 |
| 8 | TRY_JPY ← USSPX500_Futures | bb | false | 200 | 1 | 150 | 62.0 | +1.204 | 3.139 | +0.043 |
| 9 | TRY_JPY ← NQ100_Futures | bb | false | 100 | 1 | 165 | 62.4 | +1.221 | 3.135 | +0.150 |
| 10 | OIL_USD ← EUR_GBP | sma | false | 15 | 1 | 169 | 61.5 | +2.253 | 3.127 | -1.476 |

Top 10 だけを見ると、TRY_JPY が非常に目立ちます。
しかし Rank 1 / 3 / 5 / 6 / 7 は2021年以降がマイナスで、
Rank 8 / 9 だけが小幅なプラスです。

これは「過去期間で非常に綺麗に見えた戦略ほど危険」という意味ではありませんが、
**高順位だけでは regime change を見抜けない**ことをよく示しています。

## 4. 複数設定で残るペア

以下は分析用のヒューリスティックとして、上位500設定の中で同じ `(target ← ref)` が
何度現れるか、何種類の Signal で再現するか、2021年以降にどれだけ残るかをまとめたものです。

`Top500 configs` は戦略の正式な評価指標ではありません。
**パラメータを少し変えただけで消える一点最適化かどうかを見るための補助指標**です。

| Pair | Best rank | Best t | Top500 configs | Signals | 2016-20 median % | 2021+ median % | 2021+ positive configs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GBP_USD ← EUR_GBP | 11 | 3.112 | 11 | bb,change,di,sma,stoch | +0.087 | +0.218 | 100.0% |
| AUD_USD ← EUR_GBP | 13 | 3.076 | 8 | bb,change,di,sma | +0.292 | +0.180 | 87.5% |
| AUD_JPY ← EUR_GBP | 33 | 2.715 | 6 | bb,change,di,sma | +0.147 | +0.207 | 83.3% |
| OIL_USD ← GOLD_USD | 16 | 2.977 | 3 | change,sma | +2.126 | +0.397 | 100.0% |
| OIL_USD ← COPPER_USD | 19 | 2.901 | 7 | bb,change,sma,stoch | +1.578 | +0.384 | 71.4% |
| OIL_USD ← NZD_USD | 51 | 2.590 | 2 | change,sma | +1.582 | +1.060 | 100.0% |
| GBP_JPY ← USSPX500_Futures | 27 | 2.811 | 5 | bb,sma | +0.079 | +0.441 | 100.0% |
| GBP_JPY ← UK100_Futures | 14 | 3.072 | 7 | bb,sma,stoch | -0.123 | +0.279 | 85.7% |
| EUR_JPY ← AUD_NZD | 70 | 2.470 | 6 | bb,change,sma | +0.138 | +0.356 | 100.0% |
| CAD_JPY ← AUD_NZD | 39 | 2.686 | 4 | bb,change,sma | +0.116 | +0.380 | 100.0% |
| NZD_USD ← EUR_GBP | 49 | 2.614 | 4 | bb,di,sma | +0.172 | +0.201 | 100.0% |
| GBP_JPY ← EUR_GBP | 42 | 2.669 | 5 | bb,change,di,sma | -0.056 | +0.401 | 100.0% |

### 4.1 GBP_USD ← EUR_GBP

今回も最も分かりやすく残っている候補です。

- Best rank 11
- 上位500に11設定
- `bb / change / di / sma / stoch` の5種類で再現
- 上位500に入った11設定すべてが2021年以降プラス

過去分析でも繰り返し候補になっており、今回の結果でもその評価は維持されています。
単一の指標だけに依存していない点が大きな強みです。

### 4.2 AUD_USD ← EUR_GBP

これも旧分析から継続して強い候補です。

- Best rank 13
- 上位500に8設定
- 4種類の Signal で再現
- 2021年以降プラスは87.5%

GBP_USD と同じ Ref を使うため、両方を採用するときは
**EUR_GBP という同じ情報源への集中**として扱う必要があります。

### 4.3 OIL_USD ← GOLD_USD / COPPER_USD / NZD_USD

原油系は平均損益の大きさが魅力です。

- `OIL_USD ← GOLD_USD`: Best rank 16、2021+中央値 +0.397%
- `OIL_USD ← COPPER_USD`: Best rank 19、複数Signalで再現、2021+中央値 +0.384%
- `OIL_USD ← NZD_USD`: Best rank 51、2021+中央値 +1.060%

一方で原油は `worst_year_profit` の落ち込みも大きい設定があります。
**FX系の +0.x% と原油系の +1〜2% を同じリスク量として扱わない**ことが重要です。

### 4.4 EUR_JPY / CAD_JPY ← AUD_NZD

AUD_NZD を Ref にしたクロス円は、旧分析から残っているテーマです。

- `EUR_JPY ← AUD_NZD`: Best rank 70、上位500の6設定すべて2021+プラス
- `CAD_JPY ← AUD_NZD`: Best rank 39、上位500の4設定すべて2021+プラス

最高順位では EUR_GBP 系より下ですが、最近の期間まで残っている点は評価できます。

### 4.5 GBP_JPY ← USSPX500_Futures

異種アセット型の旧候補も残っています。

- Best rank 27
- 上位500に5設定
- 2021年以降は5設定すべてプラス
- 2021+中央値 +0.441%

Ref が EUR_GBP / AUD_NZD / コモディティと異なるため、
単純なランキング順位以上に **情報源の分散候補**として意味があります。

## 5. TRY_JPY 系をどう読むか

今回のランキングで一番注意すべき部分です。

`TRY_JPY ← NQ100_Futures` は上位500に19設定あり、5種類すべての Signal で再現しています。
インサンプルだけなら非常に強いです。

しかしその19設定のうち、2021年以降がプラスなのは約15.8%で、
2021+平均損益の中央値は約 -0.412% です。

`TRY_JPY ← USSPX500_Futures` も同様に上位500へ19設定ありますが、
2021年以降プラスは約15.8%、中央値は約 -0.189% です。

したがって今回の資料では、TRY_JPY 系を

> 「現在の本命」ではなく「インサンプルでは非常に強かったが、後半で regime が変わった可能性を示す教材」

として扱います。

これは Walk-forward を使う理由そのものでもあります。

## 6. 過去分析例のアーカイブ

旧 `ranking_analysis.md` の本文は今回受け取ったプロジェクトエクスポートには含まれていませんでした。
そのため、**`config.toml` に残っていた Gemini / Claude / ChatGPT の過去分析コメントを失わないよう、ここへ分析例として再整理**しています。

### 6.1 Gemini 系で挙がっていた候補

- `GBP_USD ← EUR_GBP`
  - EUR_GBP 系の代表候補。複数指標で強いと評価。
- `AUD_USD ← EUR_GBP`
  - メジャー通貨への横展開候補。
- `AUD_JPY ← EUR_GBP`
  - クロス円の分散候補。
- `OIL_USD ← GOLD_USD`
  - 長期トレンド型の高期待値候補。
- `OIL_USD ← COPPER_USD`
  - 複数指標で再現するコモディティ候補。
- `GBP_JPY ← USSPX500_Futures`
  - 米株指数とクロス円の異種アセット候補。

### 6.2 Claude 系で挙がっていた候補

本命として記録されていたもの:

- `GBP_USD ← EUR_GBP`
- `AUD_USD ← EUR_GBP`
- `CHF_JPY ← AUD_NZD`
- `GBP_JPY ← UK100_Futures`
- `OIL_USD ← NZD_USD`
- `NQ100_Futures ← USD_CHF`

第二候補:

- `EUR_JPY ← AUD_NZD`
- `GOLD_USD ← EUR_GBP`
- `OIL_USD ← COPPER_USD`

### 6.3 ChatGPT 系で挙がっていた候補

本命として記録されていたもの:

- `OIL_USD ← COPPER_USD`
- `OIL_USD ← GOLD_USD`
- `AUD_USD ← EUR_GBP`
- `GBP_USD ← EUR_GBP`
- `OIL_USD ← NZD_USD`
- `GBP_JPY ← GBP_CHF`

第二候補・追加検証:

- `OIL_USD ← SILVER_USD`
- `EUR_JPY ← AUD_NZD`
- `NZD_USD ← EUR_GBP`
- `CAD_JPY ← AUD_NZD`
- `EUR_USD ← EUR_GBP`
- `UK100_Futures ← SILVER_USD`
- `USD_JPY ← USSPX500_Futures`
- `OIL_USD ← USD_CAD`
- `US30_Futures ← SILVER_USD`
- `AUD_JPY ← GBP_CHF`
- `GBP_JPY ← AUD_NZD`

## 7. 過去候補を今回のCSVで再確認

| Past candidate | Current best rank | Best t | Top500 configs | Best row 2021+ % | Top500 2021+ positive |
| --- | --- | --- | --- | --- | --- |
| GBP_USD ← EUR_GBP | 11 | 3.112 | 11 | +0.312 | 100.0% |
| AUD_USD ← EUR_GBP | 13 | 3.076 | 8 | +0.105 | 87.5% |
| GBP_JPY ← UK100_Futures | 14 | 3.072 | 7 | +0.077 | 85.7% |
| OIL_USD ← GOLD_USD | 16 | 2.977 | 3 | +0.548 | 100.0% |
| OIL_USD ← COPPER_USD | 19 | 2.901 | 7 | +0.596 | 71.4% |
| GBP_JPY ← USSPX500_Futures | 27 | 2.811 | 5 | +0.470 | 100.0% |
| AUD_JPY ← EUR_GBP | 33 | 2.715 | 6 | +0.460 | 83.3% |
| CAD_JPY ← AUD_NZD | 39 | 2.686 | 4 | +0.378 | 100.0% |
| NZD_USD ← EUR_GBP | 49 | 2.614 | 4 | +0.015 | 100.0% |
| OIL_USD ← NZD_USD | 51 | 2.590 | 2 | +0.827 | 100.0% |
| EUR_JPY ← AUD_NZD | 70 | 2.470 | 6 | +0.246 | 100.0% |
| OIL_USD ← USD_CAD | 76 | 2.445 | 1 | +1.374 | 100.0% |
| USD_JPY ← USSPX500_Futures | 82 | 2.424 | 1 | +0.565 | 100.0% |
| UK100_Futures ← SILVER_USD | 84 | 2.418 | 3 | +0.441 | 100.0% |
| OIL_USD ← SILVER_USD | 91 | 2.386 | 3 | +0.616 | 100.0% |
| EUR_USD ← EUR_GBP | 100 | 2.340 | 5 | +0.023 | 80.0% |
| US30_Futures ← SILVER_USD | 115 | 2.292 | 2 | +0.515 | 100.0% |
| GBP_JPY ← GBP_CHF | 117 | 2.284 | 2 | +0.444 | 100.0% |
| GBP_JPY ← AUD_NZD | 135 | 2.221 | 2 | +0.329 | 100.0% |
| AUD_JPY ← GBP_CHF | 218 | 2.073 | 2 | +0.418 | 100.0% |
| CHF_JPY ← AUD_NZD | 520 | 1.768 | 0 | +0.328 |  |
| NQ100_Futures ← USD_CHF | 738 | 1.632 | 0 | -0.480 |  |
| GOLD_USD ← EUR_GBP | 1003 | 1.505 | 0 | +0.238 |  |

この表を見ると、過去候補の中でも現在まで比較的よく残っているものと、
順位が大きく下がったものがはっきり分かれます。

### 継続して強い

- `GBP_USD ← EUR_GBP`
- `AUD_USD ← EUR_GBP`
- `OIL_USD ← GOLD_USD`
- `OIL_USD ← COPPER_USD`
- `GBP_JPY ← USSPX500_Futures`
- `EUR_JPY ← AUD_NZD`
- `CAD_JPY ← AUD_NZD`

### 現時点では優先度を下げる

- `CHF_JPY ← AUD_NZD`
- `NQ100_Futures ← USD_CHF`
- `GOLD_USD ← EUR_GBP`

これらは「失敗した」と断定するのではなく、
**現在のランキング条件では以前ほど上位に残っていない**という扱いにします。

## 8. 今回の候補をどう分類するか

### A: 次の検証へ回しやすい

- `GBP_USD ← EUR_GBP`
- `AUD_USD ← EUR_GBP`
- `OIL_USD ← GOLD_USD`
- `OIL_USD ← COPPER_USD`
- `GBP_JPY ← USSPX500_Futures`
- `EUR_JPY ← AUD_NZD`
- `CAD_JPY ← AUD_NZD`

理由は、最高順位だけでなく、複数設定・複数Signal・2021年以降の残存の
いずれか複数を満たしているためです。

### B: 有望だが集中・期間依存を確認したい

- `GBP_JPY ← UK100_Futures`
- `GBP_JPY ← EUR_GBP`
- `NZD_USD ← EUR_GBP`
- `AUD_JPY ← EUR_GBP`
- `OIL_USD ← NZD_USD`
- `OIL_USD ← USD_CAD`

### C: インサンプル上位だが現在は慎重に扱う

- `TRY_JPY ← NQ100_Futures`
- `TRY_JPY ← USSPX500_Futures`
- `TRY_JPY ← GOLD_USD`
- `AUD_JPY ← EUR_AUD`
- `NZD_JPY ← EUR_AUD`

## 9. 分散という観点

ランキング上位をそのまま複数採用すると、見かけ上は別戦略でも同じ情報源へ偏ります。

### EUR_GBP クラスター

- GBP_USD
- AUD_USD
- AUD_JPY
- GBP_JPY
- NZD_USD
- EUR_USD

これらを全部採用しても、Ref が同じなので完全な分散ではありません。

### 原油クラスター

Target がすべて `OIL_USD` なら、Ref が違っても最終的な損益は原油固有リスクへ集中します。

### AUD_NZD クラスター

`EUR_JPY / CAD_JPY / GBP_JPY` など複数Targetへ展開できますが、
Ref 情報源は同じです。

将来 `max_open_positions` を再設計するときには、単純な建玉本数だけでなく、
このクラスター集中も扱う価値があります。

## 10. この分析からの次の検証

今回の `trade_ranking.csv` だけで採用を決めません。

次に候補を評価するときは、既存の Walk-forward を使って次を比較します。

1. `t_value`
2. `year_t_value`
3. `lower_confidence_bound`
4. `worst_year_pct`
5. `positive_year_ratio`
6. `half_split_min`

特に今回のように「ランキング最上位が2021年以降で崩れる」ケースでは、
年単位の一貫性を見る指標がどこまで選抜を改善するかが重要です。

## 11. 保留中の別研究: 相関・平均回帰

このランキング分析とは別に、今後行う研究テーマとして次を保留しています。

> 高相関な銘柄ペアを探索し、価格乖離が平均回帰するかを統計的に調べる。

これは現在の `target ← ref` シグナル研究とは別物です。
`correlation` が高いだけで平均回帰するとは限らないため、専用の研究プログラムで

- 相関
- スプレッド
- 乖離量
- 回帰確率
- 回帰日数
- 年代別安定性

を確認してから、優位性があれば戦略化します。

このテーマは **意図的に後回しにしている次期研究**なので、忘れず再開します。

## 12. 更新ルール

今後 `trade_ranking.csv` を作り直したら、このファイルでは次を残します。

- 過去分析の候補と当時の理由は消さない。
- 新しい結果は日付付きの章として追加する。
- 「最高順位」と「期間外で残ったか」を分ける。
- 一点の最良パラメータより、複数設定での再現を重視する。
- 過去候補が弱くなった場合も削除せず、「現在は優先度低下」と記録する。

こうすることで、相場環境が変わったときに
「何が昔は効いて、いつ弱くなったか」を追跡できるようにします。
