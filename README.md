# trade-test

複数の市場データを使って、シグナル条件の総当たりバックテスト、ランキング、
Walk-forward 検証、実運用候補シグナルの確認までを行う研究用プロジェクトです。

この README は 2026-08-22 時点のコード構成に合わせて書き直しています。

## このプロジェクトで重視すること

最優先は **分かりやすさと追跡しやすさ** です。

- UI、設定、売買計算、データ読み込み、Walk-forward の責務をできるだけ分ける。
- グローバル状態は必要最小限にする。
- 関数は一つの責務に寄せる。
- 名前から役割が分かるようにする。
- 変更時は計算結果を意図せず変えない。
- 高度な抽象化より、手で読んで直せる単純さを優先する。
- 既存ロジックを変更したら `regression_test.py` で差分を確認する。

## 現在の主要構成

```text
trade-test/
├── backtest.py
├── backtest_config.py
├── config.toml
├── strategy_screening.py
├── market_data.py
├── strategy_task.py
├── walkforward.py
├── walkforward_config.py
├── walkforward_fold.py
├── regression_test.py
├── README.md
├── ranking_analysis.md
├── trade_ranking.csv
└── stock-data/
```

### 各ファイルの責務

| ファイル | 責務 |
| --- | --- |
| `strategy_screening.py` | 全戦略組み合わせを実行し、`t_value` 順のランキングを作る |
| `backtest.py` | 1戦略の売買シミュレーションと成績集計 |
| `backtest_config.py` | 通常バックテスト用設定の読み込み、`SignalType` / `TradeCodeType` |
| `market_data.py` | 市場データ読み込みと指標キャッシュ構築 |
| `strategy_task.py` | 1戦略を表す `StrategyTask` とタスク生成 |
| `walkforward.py` | Walk-forward 選抜、未知期間評価、エクイティ、Live候補出力 |
| `walkforward_config.py` | `WalkForwardConfig` と Walk-forward 用 Enum |
| `walkforward_fold.py` | `WalkForwardFold` とフォールド生成 |
| `regression_test.py` | 固定入力から主要CSVを再生成し、Git差分で回帰確認 |
| `config.toml` | 銘柄、シグナル、期間、コスト、Walk-forward 設定の中心 |
| `ranking_analysis.md` | ランキング結果の分析記録。過去分析もアーカイブする |

## リファクタリング済みのデータ構造

以前は辞書キーや長いタプルへの依存が多くありましたが、現在は主要な構造を
名前付きの型にしています。

- `WalkForwardConfig`: Walk-forward 設定
- `WalkForwardFold`: 学習期間・検証期間
- `StrategyTask`: 1つの戦略パラメータ

また、明確な有限集合は `StrEnum` 化しています。

- `SignalType`
- `TradeCodeType`
- `WalkForwardMode`
- `SelectionMetric`
- `SelectionScope`

`StrategyTask` は `frozen=True, order=True` で、旧タプルと同じく辞書キー・比較・
ソートに使える性質を維持しています。

## 通常ランキング

### 実行

```bash
python strategy_screening.py
```

基本の流れは次の通りです。

```text
config.toml
    ↓
BackTestConfig
    ↓
build_strategy_tasks()
    ↓
market_data.build_caches()
    ↓
各 StrategyTask を backtest.run_one() で計算
    ↓
t_value 降順でランキング
    ↓
trade_ranking.csv
```

### ランキングの考え方

順位は `t_value` の降順です。

`t_value` は平均損益だけでなく、損益のばらつきと取引数も加味するため、
少数の大当たりだけで平均が高い設定を上位にしにくくする目的があります。

`ranking_period` が設定されている場合、次のランキング統計はその期間だけで計算します。

- `trade_count`
- `win_rate`
- `total_profit`
- `average_pct`
- `std_pct`
- `t_value`
- `positive_year_ratio`
- `worst_year_profit`

一方、`period_years` から作る `average_pct_YYYY_YYYY` / `trade_count_YYYY_YYYY`
の列は全履歴から作られます。ランキングに使った期間と、その前後の期間を比較するためです。

### 出力

通常は次を出力します。

```text
trade_ranking.csv
```

ランキング件数が 10,000 行を超える場合、`trade_ranking.csv` は上位10,000件、
全件は次に保存します。

```text
trade_ranking_full.csv
```

## シグナル

現在コードで扱うシグナル種別は `SignalType` で定義しています。

```text
change
sma
bb
macd
rsi
di
stoch
streak
```

実際にどれを検証するかは `config.toml` の `signal_type_list` で指定します。

指標ごとにスケールが異なるため、売買閾値は `[threshold_width]` で個別設定できます。
`rsi` / `stoch` のように中心値を持つ指標は `[threshold_center]` も利用します。

## StrategyTask

1つの戦略組み合わせは次の項目を持ちます。

```text
ref_name
target_name
signal_type
counter_trade
use_excess_return
threshold_width
hold_days
start_days
sma_period
```

`strategy_screening.py` と `walkforward.py` は同じ `build_strategy_tasks()` を使うため、
通常ランキングと Walk-forward でタスク生成条件がずれにくい構造になっています。

## Walk-forward 検証

### 実行

```bash
python walkforward.py
```

過去期間だけで戦略を選び、その直後の未知期間だけで成績を評価します。
これを時間方向に繰り返すことで、全期間を見てから勝者を選ぶ過剰最適化を減らします。

### Walk-forward の主要設定

`[walkforward]` では次を設定します。

- `train_years`: 学習・選抜期間
- `test_years`: 未知期間
- `step_years`: 前進幅
- `mode`: `anchored` / `rolling`
- `select_metric`: 選抜指標
- `select_per`: `target` / `global`
- `select_top_k`: 選抜本数
- `min_is_trades`: 学習期間の最低取引数
- `min_is_t`: 品質ゲート
- `max_open_positions`: ポートフォリオ全体の最大同時建玉数。0は無制限

### SelectionMetric

現在の選抜指標は次です。

| 値 | 意味 |
| --- | --- |
| `t_value` | 取引単位の t値 |
| `year_t_value` | 年平均を1サンプルとした t値 |
| `lower_confidence_bound` | 平均から標準誤差を割り引く |
| `average_pct` | 平均損益率 |
| `total_pct` | 損益率合計 |
| `worst_year_pct` | 学習期間の最悪年を重視 |
| `positive_year_ratio` | 陽性年比率と平均の合成 |
| `half_split_min` | 学習期間の前半・後半の弱い方を評価 |

### Walk-forward 出力

```text
walkforward_{select_metric}.csv
live_signals.csv
```

`walkforward_*.csv` は未知期間のトレード、選抜時の学習成績、フォールド情報を
一つの統合表として持ちます。

`live_signals.csv` は直近学習期間で選ばれた戦略について、現在の候補を出力します。

```text
PENDING : シグナル確定済み、まだ未エントリー
OPEN    : 現在保有中
CLOSED  : 直近の決済済みトレード
```

## max_open_positions について

`max_open_positions` は現在も使用しますが、**アルゴリズムの再設計は保留中**です。

現状はポートフォリオ全体の同時建玉数を制限し、同日の候補では学習時点の
`selection_score` が高いものを優先します。

将来、次の問題を本格的に扱う段階で再検討します。

- 同一銘柄への集中
- 同一 Ref / Target への集中
- 戦略間相関
- 資金配分
- リスク量ベースの建玉制限

## 回帰テスト

### 実行

```bash
python regression_test.py
```

固定入力から次を再生成します。

- 通常ランキング
- `lower_confidence_bound`
- `year_t_value`
- `worst_year_pct`
- `positive_year_ratio`
- `half_split_min`
- `t_value`

テストスクリプト自体は数値差分を判定しません。

```text
regression_test.py
    ↓
主要CSVを再生成
    ↓
git diff
    ↓
意図しない変更がないことを確認
```

リファクタリングではこの方法で各段階の結果が変わっていないことを確認しています。

## 注意点

### use_excess_return

`use_excess_return=true` のドリフトは現在、全期間平均から計算されます。
厳密な leak-free 評価を行う場合は注意が必要です。
Walk-forward 側もこの条件を検出すると警告を表示します。

### 売買コスト

`config.toml` の `[symbols]` にある `cost` / `swap` を利用します。
値が 0 または未設定の銘柄は、現実の摩擦を十分に反映していない可能性があります。
結果を見るときは必ず確認してください。

### ランキングだけで採用しない

`trade_ranking.csv` は候補探索用です。
高い `t_value` は将来の利益を保証しません。

最終判断では少なくとも、

1. 期間別成績
2. 複数パラメータでの再現性
3. 複数シグナルでの再現性
4. Walk-forward
5. コスト耐性
6. 戦略同士の集中

を確認します。

## 現在の開発状況

2026-08-22 時点で、主要な構造リファクタリングは一段落しています。

完了済み:

- `WalkForwardConfig` dataclass 化
- `WalkForwardFold` dataclass 化
- `StrategyTask` dataclass 化
- タスク生成処理の共通化
- 明確な有限集合の Enum 化
- 各段階の回帰テスト

今後は「コードを綺麗にすること」自体を目的にせず、新しい研究や機能追加で
実際に邪魔になった箇所を必要な分だけ整理します。

## 保留中の次期研究: 高相関ペアと平均回帰

**重要: このテーマは未着手ではなく、意図的に後回しにしている次の研究テーマです。**

再開するときは、まず既存バックテストへ直接組み込まず、研究専用プログラムを作ります。
仮のファイル名は次です。

```text
pair_research.py
```

研究の順序:

```text
1. 高相関な銘柄ペアを探索
2. 価格差・価格比・スプレッドを定義
3. 乖離量を測る
4. 乖離後に平均へ戻る確率を測る
5. 回帰までの日数を測る
6. 年代別に性質が安定しているか確認
7. 現象が十分に強ければ単純な売買戦略へ昇格
8. 既存 Walk-forward で検証
```

注意点は、**高相関だから平均回帰するとは限らない**ことです。
最初から売買ルールを最適化せず、まず現象そのものが存在するかを検証します。

この研究を再開するときのキーワードは、

> 「高相関ペアの乖離・平均回帰研究を再開する」

です。

## 関連資料

- `ranking_analysis.md`: 通常ランキングの分析と過去候補の記録
- `trade_ranking.csv`: 現在のランキング結果
- `walkforward_*.csv`: 未知期間評価
- `live_signals.csv`: 現在の候補シグナル
