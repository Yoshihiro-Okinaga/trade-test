# リード・ラグ戦略 検証システム

ある銘柄 `ref`（シグナル源）の指標を見て、別銘柄 `target`（売買対象）を仕掛ける
クロス銘柄リード・ラグ戦略を、総当たりで探索し、walk-forward で過剰最適化を剥がして
評価するためのツール群。

> このドキュメントは**現行コードの実態**に合わせて整理したもの（使い方・ファイル構成・
> 出力）。これまでの検証で確定した結論は「8. 検証記録」に保全してある。

---

## 1. システム構成（ファイル）

| ファイル | 役割 |
|---------|------|
| `backtest.py` | 売買シミュレーション本体。`calc_trade_results` が、ある (ref, target, 指標, パラメータ) について全履歴のトレードを計算し、片道コスト＋スワップ差引後の損益を返す。 |
| `backtest_config.py` | 設定の読み込み（`BackTestConfig`）と指標定義（`SignalType`）。銘柄・コスト、`cost_of` / `swap_of`、OS別の保存先解決を持つ。 |
| `market_data.py` | `stock-data/Manual` 配下の価格CSVを読み、指標キャッシュを構築。 |
| `main.py` | 総当たりランキング。`ranking_period` の期間で全組み合わせを集計し、`trade_ranking.csv` を出力。 |
| `walkforward.py` | walk-forward 検証（学習→未知期間で評価を前進反復）。統合表を1枚出力。`live` サブコマンドで実運用シグナルも出せる。 |
| `check_dates.py` | 独立ツール。データフォルダ内の全CSVを調べ、日付（行数）が極端に少ない銘柄を一覧化。ユニバースから外す判断に使う。 |
| `test_regression.py` | ゴールデン方式の回帰テスト。リファクタ前後で `main.py` の出力が変わっていないかCSV比較で確認。 |

---

## 2. データ

- 場所：`stock-data/Manual/`（サブフォルダも再帰的に読む）。1銘柄1CSV。
- 必須列：`日付` / `終値` / `高値` / `安値`。日付でパースし、欠損行は落とす。
- ユニバースは `config.toml` の `symbol_groups`（現在 **fx / index / commodity**）や
  `symbol_names` / `symbol_pairs` で選ぶ。
- 履歴が短い銘柄はフォールドの比較を歪めるので、投入前に `check_dates.py` で確認する。

---

## 3. 使い方（コマンド）

### 総当たりランキング（in-sample）
```
python main.py
```
- `ranking_period`（例 `[2001, 2015]`）の期間で全組み合わせを集計し、`t_value` などで並べる。
- 出力：`trade_ranking.csv`（行数が1万超なら `trade_ranking_full.csv` に全行も）。
- `period_years` を設定すると、5年区切りなどの**期間別平均**も列に付く（エッジの時間構造の確認用）。
- 注意：これは**全期間当てはめ＝過剰最適化を含む**見方。ここで良く見えた候補は「仮説」。

### walk-forward 検証（out-of-sample）
```
python walkforward.py
```
- 学習窓で戦略を選び、その直後の**未使用の検証窓**で成績を記録。時間をずらして繰り返す。
- `ranking_period` を尊重する（例 `[2001, 2020]` なら 2021 以降は温存＝最終テスト用に手つかず）。
- 出力：**統合表 `walkforward_{metric}.csv` の1枚**（下記「出力」参照）。
- コンソール：フォールド別成績・全体の残存率/平均/t・閾値スキャン・最大ドローダウン。

### 実運用シグナル（今どう売買するか）
```
python walkforward.py live
```
- 直近 `train_years` 年で「今の最良戦略」を選び、それが**現在出しているシグナル**を表示：
  現在のオープン建玉・本日の新規シグナル・直近の決済済みトレード。
- 出力：`live_signals.csv`。`ranking_period` に関係なく常に**最新データ**を基準にする。
- これは検証とは別の実行で、「もし今 running させたら何を建てるか」を体感するためのもの。

### データ被覆チェック
```
python check_dates.py stock-data/Manual        # 既定しきい値500行
python check_dates.py stock-data/Manual 2000    # しきい値を指定
```
- 標準ライブラリのみで動く独立スクリプト。日付の少ない銘柄を少ない順に一覧＋除外候補を出す。

### 回帰テスト
```
python main.py
cp trade_ranking.csv golden.csv                        # 変更前を正解として保存
# …コードを変更…
python test_regression.py golden.csv trade_ranking.csv # 差分ゼロなら PASS
```

---

## 4. 出力ファイル

保存先は OS で切り替わる（`walkforward.py` / `main.py` の先頭で決定）：
- Mac：`~/Dropbox/Private/trade_test_results/`（自動作成・共有向け）
- それ以外：`../TestResult/`（**存在しないと書き出しで落ちるので先に作成**）

| 出力 | 内容 |
|------|------|
| `trade_ranking.csv` | main.py の総当たりランキング（in-sample）。 |
| `walkforward_{metric}.csv` | **統合表**。1行 = 1未知トレード＋その戦略のメタ情報（signal_type / counter_trade / hold_days …）＋学習成績（is_trades / is_mean_pct / is_t / is_years）＋トレード（entry/exit/profit/cumulative）。OOSトレードが0だった選抜戦略も、トレード列を空にして1行残す。<br>旧 `walkforward_selection/summary/equity` の3枚はこの1枚の集計ビューに相当し、フォールド別成績・選抜一覧・累積リターンはここから再現できる。 |
| `live_signals.csv` | live モードの現在の建玉・新規シグナル・直近決済。 |

---

## 5. 主要な設定（config.toml）

**探索グリッド（上部）**
- `symbol_groups` … 対象グループ（fx / index / commodity）。
- `signal_type_list` … 現在は `change / sma / bb / rsi / di / stoch` の**6種**を探索。
  （エンジンの `SignalType` は macd / streak も対応。adx はコメントアウト。使うなら list に追加。）
- `hold_days_list` / `start_days_list` / `sma_period_list` / `threshold_width` … 掛け合わせて総当たり。
- `counter_trade = [true, false]` … 逆張り・順張りの両方を探索。
- `no_overlap = true` … 同方向の建玉が重ならないよう補正。
- `ranking_period` … 解析対象の年範囲。main.py のランキング窓であり、walk-forward のフォールドもこの範囲に収める。
- `filter_signal_type` / `filter_max` … 任意。ref 側の指標が閾値以下の日だけ仕掛ける絞り込み（空で無効）。

**[walkforward] セクション**
- `train_years = 8` / `test_years = 2` / `step_years = 2` / `mode = "rolling"`
  （`rolling`＝固定長スライド、`anchored`＝開始固定で窓が拡大）
- `select_metric` … `t_value` / `year_t_value` / `lower_confidence_bound` / `average_pct` / `total_pct`
- `select_per`（target / global）/ `select_top_k`
- `min_is_trades = 30` / `min_is_t = 2.0` … 選抜の品質ゲート（学習期間の最小取引数・最小t値）。

---

## 6. コストの扱い

- backtest は損益から**片道スプレッド**（`TRADE_COST`）と**スワップ**を最初から引いている
  （`backtest.py` の profit 計算）。したがって walk-forward の**全 OOS 値はコスト後の手取り**。
- スプレッドは「買った瞬間に不利な位置から入る」コストなので**片道1回が正しい**
  （決済は通常返るので往復2辺目を引くのは誤り）。FX・Index・Commodity はスプレッド商品。
- `extra_cost_pct`（config、既定オフ）で、追加摩擦を一律に上乗せして頑健性を試せる（検証用のつまみ）。
- 残る現実の摩擦はスリッページ（約定ずれ）。実約定データが要るため「運用しながら実測」する性質。

---

## 7. 方法論と規律

- **学習と検証の分離**：walk-forward は選抜に使う情報を「その時点までの過去」に限定する。
  main.py の全期間ランキングは全期間を見て勝者を選ぶため、優位性を過大評価する（＝過剰最適化）。
- **anchored vs rolling**：anchored は後半フォールドが同じ前半履歴を共有し、独立な証拠になりにくい
  （実質「一つの長い当てはめ」）。rolling の方が正直で厳しい。
- **ゲートを OOS で選ばない**：`min_is_t` や期間などを「OOS の成績を見て」選ぶのは、学習と検証の
  分離を自分で破ること。段階検証（main → walkforward で ranking_period を狭める → 全期間で最終テスト）
  の順序を守る。
- **後付け選抜に注意**：OOS 列を眺めて拾った候補はすべて仮説。独立した切り分けを通すまで信用しない。
- **自動判定を鵜呑みにしない**：nan や「候補なし」で結論が逆になる事例があった。集計行と突き合わせて目視確認。
- **t値は各トレードを独立とみなす近似**（トレード間・銘柄間の相関は補正しない）。相対比較の目安として使う。

---

## 8. 検証記録（これまでに確定した結論）

> 以下は過去の検証で得た結論の記録。当時使った切り分け・相関の一部の補助スクリプトは
> 現在のツリーには含まれていない（分析結果のみ保全）。

- 検証を通った軸は **①（GBP_USD ← EUR_GBP）** と **④（AUD_USD ← EUR_GBP）** の2本。
  - ①：効いているのは「EUR 対 GBP の相対」そのもの（GBP_USD 自身でも EUR_USD 単独でもない）。
    寿命は数年スケール。rolling 8→2 の OOS で概ね +0.23% / t≈1.9。
  - ④：参照関係そのものにエッジが宿り（特定指標に依存しない）、①より近年型で時間的に安定。
    共有通貨ゼロ（EUR/GBP と AUD/USD）＝算術連動でない本物のクロス市場関係。OOS 概ね +0.18%。
- **①④の集中リスク**：日次損益の相関 ρ≈0.30（同時稼働日で 0.39）。合わせて持つと**実質1.7本分**。
  発火源が同じ EUR_GBP なので分散は完全ではない。
- **不採用**：
  - ★（USD_CHF ← CAD_JPY, bb逆）… ①④と無相関という魅力はあったが本体が弱い。見かけのプラスは
    2015-2016 の単発当たり依存で、2021- でほぼ消滅。**無相関はエッジが本物で初めて価値になる**。
  - ③（USD_JPY ← GBP_AUD, bb）… OOS が期間の過半でマイナス、近年マイナス転落。
  - ②（NZD_USD ← EUR_GBP, rsi）… 物語（逆張り）とルール（順張り）が矛盾、実績も薄い。
- **EUR_GBP は広域シグナル**だが、裏を返せば EUR_GBP 発火の別 target を足しても「同じ源への露出」で
  分散にならない。独立源（例：株指数×株指数、商品×商品）は別途 walk-forward で検証が要る。

### 残る宿題
1. **サイズ設計** … 実質1.7本分のリスク配分、同時発火時の扱い（検証でなく設計）。
2. **危機時の相関上昇** … ρ0.30 は平時の平均。2020年3月のような一斉変動時に跳ねうる。
3. **スリッページの実測** … 運用しながらモデルにフィードバックする性質。
4. **Index / Commodity の基盤検証** … これらは現在ユニバースに入っているが、コスト設定・データ品質が
   FX と同水準に検証されているかは要確認。独立源候補（例 NQ100←US30 等）を追う前提として先に固める。

---

## 補足：関連ファイル

- `ranking_analysis.md` … `trade_ranking` の in-sample 分析メモ（期間別のエッジ時間構造、独立源候補）。
