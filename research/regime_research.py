import argparse
import math
import os
import sys
import tomllib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# このファイルを research/ から直接実行しても、
# プロジェクト直下の backtest.py / market_data.py などを読めるようにする。
RESEARCH_DIR = Path(__file__).resolve().parent
PROJECT_DIR = RESEARCH_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import backtest
from backtest_config import BackTestConfig
from market_data import MarketData
from strategy_task import StrategyTask


MAX_WORKERS = min(32, os.cpu_count() or 1)
ROUND_DIGITS = 9

SELECTED_OUTPUT_FILE = "regime_selected_strategies.csv"
TRADE_OUTPUT_FILE = "regime_trades.csv"
SUMMARY_OUTPUT_FILE = "regime_summary.csv"
COMPARISON_OUTPUT_FILE = "regime_comparison.csv"


@dataclass(frozen=True)
class RegimeResearchConfig:
    periods: tuple[tuple[int, int], ...]
    pairs: tuple[tuple[str, str], ...]
    volatility_window: int
    volatility_baseline_window: int
    direction_sma_window: int
    min_trades_per_regime: int

    @classmethod
    def from_config_data(cls, config_data: dict):
        raw = config_data.get("regime_research", {})

        raw_periods = raw.get("periods")
        if raw_periods is None:
            # 旧設定との互換性。period = [2016, 2020] も引き続き使える。
            raw_periods = [raw.get("period", [2016, 2020])]

        periods = _parse_periods(raw_periods)

        pairs = _parse_pairs(raw.get("pairs", []))
        if not pairs:
            raise ValueError(
                "regime_research.pairs に調べる target/ref を指定してください。"
            )

        volatility_window = int(raw.get("volatility_window", 20))
        volatility_baseline_window = int(
            raw.get("volatility_baseline_window", 252)
        )
        direction_sma_window = int(raw.get("direction_sma_window", 200))
        min_trades_per_regime = int(raw.get("min_trades_per_regime", 5))

        for name, value in [
            ("volatility_window", volatility_window),
            ("volatility_baseline_window", volatility_baseline_window),
            ("direction_sma_window", direction_sma_window),
            ("min_trades_per_regime", min_trades_per_regime),
        ]:
            if value < 1:
                raise ValueError(f"regime_research.{name} は1以上にしてください。")

        return cls(
            periods=periods,
            pairs=pairs,
            volatility_window=volatility_window,
            volatility_baseline_window=volatility_baseline_window,
            direction_sma_window=direction_sma_window,
            min_trades_per_regime=min_trades_per_regime,
        )


def _parse_periods(raw_periods) -> tuple[tuple[int, int], ...]:
    """分析期間を検証し、重複しない昇順の期間として返す。"""
    periods = []

    for raw_period in raw_periods:
        if len(raw_period) != 2:
            raise ValueError(
                "regime_research.periods の各要素は "
                "[開始年, 終了年] にしてください。"
            )

        start_year = int(raw_period[0])
        end_year = int(raw_period[1])
        if start_year > end_year:
            raise ValueError(
                "regime_research.periods は 開始年 <= 終了年 にしてください。"
            )

        periods.append((start_year, end_year))

    if not periods:
        raise ValueError(
            "regime_research.periods に1つ以上の期間を指定してください。"
        )

    if periods != sorted(periods):
        raise ValueError(
            "regime_research.periods は古い期間から順に指定してください。"
        )

    for previous, current in zip(periods, periods[1:]):
        if previous[1] >= current[0]:
            raise ValueError(
                "regime_research.periods は重複しない期間にしてください。"
            )

    return tuple(periods)


def _parse_pairs(raw_pairs) -> tuple[tuple[str, str], ...]:
    """設定の pairs を (ref, target) の組へ変換する。"""
    pairs = []
    seen = set()

    for raw_pair in raw_pairs:
        if isinstance(raw_pair, dict):
            target = raw_pair.get("target")
            ref = raw_pair.get("ref")
        else:
            if len(raw_pair) != 2:
                raise ValueError(
                    f"regime_research.pairs の要素が不正です: {raw_pair!r}"
                )
            target, ref = raw_pair

        if not target or not ref:
            raise ValueError(
                "regime_research.pairs には target と ref が必要です。"
            )

        pair = (str(ref), str(target))
        if pair in seen:
            raise ValueError(
                f"regime_research.pairs に重複があります: "
                f"target={target}, ref={ref}"
            )

        seen.add(pair)
        pairs.append(pair)

    return tuple(pairs)


def default_save_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Dropbox" / "Private" / "trade_test_results"
    return Path("./")


def load_config(config_path: Path) -> dict:
    try:
        with open(config_path, "rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"config.toml が見つかりません: {config_path}"
        ) from None


def validate_periods(
    backtest_config: BackTestConfig,
    regime_config: RegimeResearchConfig,
):
    if not backtest_config.ranking_period:
        raise ValueError(
            "レジーム研究では戦略選抜期間を固定するため、"
            "ranking_period を指定してください。"
        )

    selection_start, selection_end = backtest_config.ranking_period

    for period in regime_config.periods:
        start_year, end_year = period

        within_selection = (
            start_year >= selection_start
            and end_year <= selection_end
        )
        after_selection = start_year > selection_end

        if not within_selection and not after_selection:
            raise ValueError(
                "分析期間は ranking_period の内部に完全に収めるか、"
                "ranking_period 終了後にしてください。"
                f" ranking_period={backtest_config.ranking_period}, "
                f"analysis_period={list(period)}"
            )


def period_label(period: tuple[int, int]) -> str:
    return f"{period[0]}_{period[1]}"


def period_role(
    period: tuple[int, int],
    selection_period,
) -> str:
    """分析期間が戦略選抜内か、選抜後OOSかを明示する。"""
    if period[1] <= selection_period[1]:
        return "selection_subperiod"
    return "oos"


def build_candidate_tasks(
    config: BackTestConfig,
    regime_config: RegimeResearchConfig,
) -> list[StrategyTask]:
    """レジーム研究の pairs から候補タスクを直接作る。

    通常バックテスト用の symbol_pairs は現在の運用・検証設定なので、
    レジーム研究の対象選定には使わない。シグナル種別や各パラメータ候補は
    通常設定を共有し、ペアだけを regime_research.pairs から受け取る。
    """
    undefined = []
    for ref_name, target_name in regime_config.pairs:
        for name in (ref_name, target_name):
            if name not in config.symbols and name not in undefined:
                undefined.append(name)

    if undefined:
        raise ValueError(
            "regime_research.pairs に symbols 未定義の銘柄があります: "
            + ", ".join(undefined)
        )

    # use_excess_return=true は現行実装では全期間平均ドリフトを使うため、
    # 全期間平均ドリフトによる未来参照を避けるため、false だけを作る。
    return [
        StrategyTask(
            ref_name=ref_name,
            target_name=target_name,
            signal_type=signal_type,
            counter_trade=counter_trade,
            use_excess_return=False,
            threshold_width=threshold_width,
            hold_days=hold_days,
            start_days=start_days,
            sma_period=sma_period,
        )
        for ref_name, target_name in regime_config.pairs
        for signal_type in config.signal_type_list
        for counter_trade in config.counter_trade
        for threshold_width in config.widths_of(signal_type)
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]


def build_task_caches(tasks: list[StrategyTask], data_folder=None):
    """今回使うタスクに必要なキャッシュだけ作る。"""
    ref_cache = {}
    target_cache = {}
    market_data_cache = {}

    def get_market_data(name: str):
        if name not in market_data_cache:
            market_data_cache[name] = MarketData(name, data_folder)
        return market_data_cache[name]

    for task in tasks:
        ref_key = (
            task.ref_name,
            task.start_days,
            task.sma_period,
        )
        if ref_key not in ref_cache:
            ref_data = get_market_data(task.ref_name)
            ref_cache[ref_key] = ref_data.calc_ref_signals(
                task.start_days,
                task.sma_period,
            )

        target_key = (
            task.target_name,
            task.hold_days,
        )
        if target_key not in target_cache:
            target_data = get_market_data(task.target_name)
            target_cache[target_key] = target_data.calc_target_prices(
                task.hold_days
            )

    return ref_cache, target_cache


def run_selection_tasks(
    config: BackTestConfig,
    tasks: list[StrategyTask],
    ref_cache,
    target_cache,
):
    """2001-2015等の ranking_period だけで各候補戦略を評価する。"""
    rows = []

    if config.use_process_pool:
        chunksize = max(1, len(tasks) // (MAX_WORKERS * 8))
        with ProcessPoolExecutor(
            max_workers=MAX_WORKERS,
            initializer=backtest.init_worker,
            initargs=(config, ref_cache, target_cache),
        ) as executor:
            results = executor.map(
                backtest.run_one_shared,
                tasks,
                chunksize=chunksize,
            )
            for task, result in zip(tasks, results):
                if result is not None:
                    rows.append((task, result))
    else:
        backtest.init_worker(config, ref_cache, target_cache)
        for task in tasks:
            result = backtest.run_one(config, task)
            if result is not None:
                rows.append((task, result))

    return rows


def select_best_per_pair(
    selection_rows,
    regime_config: RegimeResearchConfig,
):
    """各 target/ref から IS t_value が最も高い1戦略だけを固定する。"""
    grouped = {
        pair: []
        for pair in regime_config.pairs
    }

    for task, result in selection_rows:
        pair = (task.ref_name, task.target_name)
        if pair in grouped:
            grouped[pair].append((task, result))

    selected = []
    for pair in regime_config.pairs:
        candidates = grouped[pair]
        if not candidates:
            ref, target = pair
            raise ValueError(
                f"選抜条件を満たす戦略がありません: {target} ← {ref}"
            )

        candidates.sort(
            key=lambda item: (
                -_finite_or_minus_inf(item[1].get("t_value")),
                item[0],
            )
        )
        selected.append(candidates[0])

    return selected


def _finite_or_minus_inf(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float("-inf")
    return value if math.isfinite(value) else float("-inf")


def build_selected_strategy_frame(selected_rows) -> pd.DataFrame:
    rows = []

    for task, result in selected_rows:
        rows.append({
            "target": task.target_name,
            "ref": task.ref_name,
            "signal_type": task.signal_type,
            "counter_trade": task.counter_trade,
            "use_excess_return": task.use_excess_return,
            "threshold_width": task.threshold_width,
            "hold_days": task.hold_days,
            "start_days": task.start_days,
            "sma_period": task.sma_period,
            "is_trade_count": result.get("trade_count"),
            "is_average_pct": result.get("average_pct"),
            "is_win_rate": result.get("win_rate"),
            "is_t_value": result.get("t_value"),
            "is_worst_year_profit": result.get("worst_year_profit"),
            "is_positive_year_ratio": result.get(
                "positive_year_ratio"
            ),
        })

    return pd.DataFrame(rows)


def build_regime_frame(
    target_name: str,
    regime_config: RegimeResearchConfig,
    data_folder=None,
) -> pd.DataFrame:
    """Target自身の過去データだけで、その日の市場状態を作る。

    エントリー当日の終値を見てから分類すると未来情報になるため、
    計算した状態を1営業日 shift し、前営業日までに分かる情報だけを
    entry_date に付与する。
    """
    data = MarketData(target_name, data_folder).df[
        ["日付", "終値"]
    ].copy()

    close = pd.to_numeric(data["終値"], errors="coerce")
    log_return = np.log(close).diff()

    realized_vol = log_return.rolling(
        regime_config.volatility_window
    ).std()

    volatility_baseline = realized_vol.rolling(
        regime_config.volatility_baseline_window
    ).median()

    direction_sma = close.rolling(
        regime_config.direction_sma_window
    ).mean()

    known_vol = realized_vol.shift(1)
    known_vol_baseline = volatility_baseline.shift(1)
    known_close = close.shift(1)
    known_sma = direction_sma.shift(1)

    data["regime_volatility"] = np.where(
        known_vol.isna() | known_vol_baseline.isna(),
        None,
        np.where(
            known_vol >= known_vol_baseline,
            "high_vol",
            "low_vol",
        ),
    )

    data["regime_direction"] = np.where(
        known_close.isna() | known_sma.isna(),
        None,
        np.where(
            known_close >= known_sma,
            "up",
            "down",
        ),
    )

    data["regime_combined"] = (
        data["regime_volatility"].fillna("")
        + "_"
        + data["regime_direction"].fillna("")
    )
    invalid = (
        data["regime_volatility"].isna()
        | data["regime_direction"].isna()
    )
    data.loc[invalid, "regime_combined"] = None

    data["known_realized_vol"] = known_vol
    data["known_volatility_baseline"] = known_vol_baseline
    data["known_price_vs_sma_pct"] = (
        (known_close - known_sma) / known_sma * 100
    )

    return data[[
        "日付",
        "regime_volatility",
        "regime_direction",
        "regime_combined",
        "known_realized_vol",
        "known_volatility_baseline",
        "known_price_vs_sma_pct",
    ]]


def run_selected_strategy(
    config: BackTestConfig,
    task: StrategyTask,
):
    trades, _, _ = backtest.calc_trade_results(
        config,
        False,
        *task.as_backtest_args(),
    )
    if trades is None:
        return pd.DataFrame()
    return trades.copy()


def restrict_to_evaluation_period(
    trades: pd.DataFrame,
    period: tuple[int, int],
) -> pd.DataFrame:
    start_year, end_year = period

    # Walk-forward と同じ考え方で、評価期間内に完結したトレードだけ使う。
    return trades[
        (trades["entry_year"] >= start_year)
        & (trades["exit_year"] <= end_year)
        & (~trades["is_open"])
        & trades["profit_pct"].notna()
    ].copy()


def attach_regime(
    trades: pd.DataFrame,
    regime_frame: pd.DataFrame,
) -> pd.DataFrame:
    return trades.merge(
        regime_frame,
        left_on="entry_date",
        right_on="日付",
        how="left",
    ).drop(columns=["日付"])


def add_strategy_columns(
    trades: pd.DataFrame,
    task: StrategyTask,
    selection_result: dict,
    period: tuple[int, int],
    role: str,
) -> pd.DataFrame:
    trades = trades.copy()
    trades.insert(0, "target", task.target_name)
    trades.insert(1, "ref", task.ref_name)
    trades.insert(2, "signal_type", task.signal_type)
    trades.insert(3, "counter_trade", task.counter_trade)
    trades.insert(4, "threshold_width", task.threshold_width)
    trades.insert(5, "hold_days", task.hold_days)
    trades.insert(6, "start_days", task.start_days)
    trades.insert(7, "sma_period", task.sma_period)
    trades.insert(8, "is_t_value", selection_result.get("t_value"))
    trades.insert(9, "analysis_period", period_label(period))
    trades.insert(10, "analysis_start_year", period[0])
    trades.insert(11, "analysis_end_year", period[1])
    trades.insert(12, "period_role", role)
    return trades


def summarize_trades(
    trades: pd.DataFrame,
    task: StrategyTask,
    selection_result: dict,
    regime_config: RegimeResearchConfig,
    period: tuple[int, int],
    role: str,
) -> list[dict]:
    rows = []

    position_groups = [
        ("all", trades),
        ("long", trades[trades["position"] == "long"]),
        ("short", trades[trades["position"] == "short"]),
    ]

    for position_scope, position_trades in position_groups:
        rows.append(
            summarize_group(
                position_trades,
                task,
                selection_result,
                regime_config,
                period,
                role,
                position_scope,
                "overall",
                "all",
            )
        )

        for axis, column in [
            ("volatility", "regime_volatility"),
            ("direction", "regime_direction"),
            ("combined", "regime_combined"),
        ]:
            valid = position_trades[
                position_trades[column].notna()
            ]
            for regime_name, group in valid.groupby(
                column,
                sort=True,
            ):
                rows.append(
                    summarize_group(
                        group,
                        task,
                        selection_result,
                        regime_config,
                        period,
                        role,
                        position_scope,
                        axis,
                        regime_name,
                    )
                )

    return rows


def summarize_group(
    group: pd.DataFrame,
    task: StrategyTask,
    selection_result: dict,
    regime_config: RegimeResearchConfig,
    period: tuple[int, int],
    role: str,
    position_scope: str,
    regime_axis: str,
    regime_name: str,
) -> dict:
    profit_pct = pd.to_numeric(
        group["profit_pct"],
        errors="coerce",
    ).dropna()

    trade_count = len(profit_pct)
    average_pct = profit_pct.mean() if trade_count else float("nan")
    median_pct = profit_pct.median() if trade_count else float("nan")
    std_pct = (
        profit_pct.std(ddof=1)
        if trade_count > 1
        else float("nan")
    )
    win_rate = (
        (profit_pct > 0).mean() * 100
        if trade_count
        else float("nan")
    )

    if (
        trade_count > 1
        and pd.notna(std_pct)
        and std_pct > 0
    ):
        t_value = average_pct / std_pct * math.sqrt(trade_count)
    else:
        t_value = float("nan")

    return {
        "target": task.target_name,
        "ref": task.ref_name,
        "signal_type": task.signal_type,
        "counter_trade": task.counter_trade,
        "threshold_width": task.threshold_width,
        "hold_days": task.hold_days,
        "start_days": task.start_days,
        "sma_period": task.sma_period,
        "is_t_value": selection_result.get("t_value"),
        "analysis_period": period_label(period),
        "analysis_start_year": period[0],
        "analysis_end_year": period[1],
        "period_role": role,
        "position_scope": position_scope,
        "regime_axis": regime_axis,
        "regime": regime_name,
        "trade_count": trade_count,
        "enough_trades": (
            trade_count >= regime_config.min_trades_per_regime
        ),
        "average_pct": average_pct,
        "median_pct": median_pct,
        "win_rate": win_rate,
        "std_pct": std_pct,
        "t_value": t_value,
        "sum_profit_pct": profit_pct.sum(),
        "long_count": int((group["position"] == "long").sum()),
        "short_count": int((group["position"] == "short").sum()),
    }


def build_comparison_frame(summary: pd.DataFrame) -> pd.DataFrame:
    """期間ごとの high-low / down-up 差を見やすい1行形式にする。"""
    if summary.empty:
        return pd.DataFrame()

    key_columns = [
        "target",
        "ref",
        "signal_type",
        "counter_trade",
        "threshold_width",
        "hold_days",
        "start_days",
        "sma_period",
        "is_t_value",
        "analysis_period",
        "analysis_start_year",
        "analysis_end_year",
        "period_role",
        "position_scope",
    ]

    rows = []
    for key, group in summary.groupby(
        key_columns,
        dropna=False,
        sort=False,
    ):
        row = dict(zip(key_columns, key))

        def value(axis, regime, column):
            matched = group[
                (group["regime_axis"] == axis)
                & (group["regime"] == regime)
            ]
            if matched.empty:
                return float("nan")
            return matched.iloc[0][column]

        for regime_name in [
            "high_vol",
            "low_vol",
            "down",
            "up",
        ]:
            axis = (
                "volatility"
                if regime_name in {"high_vol", "low_vol"}
                else "direction"
            )
            row[f"{regime_name}_trade_count"] = value(
                axis,
                regime_name,
                "trade_count",
            )
            row[f"{regime_name}_average_pct"] = value(
                axis,
                regime_name,
                "average_pct",
            )
            row[f"{regime_name}_median_pct"] = value(
                axis,
                regime_name,
                "median_pct",
            )
            row[f"{regime_name}_win_rate"] = value(
                axis,
                regime_name,
                "win_rate",
            )

        row["high_minus_low_average_pct"] = (
            row["high_vol_average_pct"]
            - row["low_vol_average_pct"]
        )
        row["down_minus_up_average_pct"] = (
            row["down_average_pct"]
            - row["up_average_pct"]
        )

        overall = group[
            (group["regime_axis"] == "overall")
            & (group["regime"] == "all")
        ]
        if overall.empty:
            row["overall_trade_count"] = float("nan")
            row["overall_average_pct"] = float("nan")
            row["overall_median_pct"] = float("nan")
        else:
            overall_row = overall.iloc[0]
            row["overall_trade_count"] = overall_row["trade_count"]
            row["overall_average_pct"] = overall_row["average_pct"]
            row["overall_median_pct"] = overall_row["median_pct"]

        rows.append(row)

    return pd.DataFrame(rows)


def print_selected_strategies(
    selected_frame: pd.DataFrame,
    selection_period,
):
    print("\n=== 過去期間だけで固定した戦略 ===")
    print(
        f"選抜期間: {selection_period[0]}～{selection_period[1]}"
    )

    columns = [
        "target",
        "ref",
        "signal_type",
        "counter_trade",
        "threshold_width",
        "sma_period",
        "is_trade_count",
        "is_average_pct",
        "is_t_value",
    ]
    print(selected_frame[columns].to_string(index=False))


def print_regime_highlights(comparison: pd.DataFrame):
    if comparison.empty:
        print("\n比較できるレジーム成績がありません。")
        return

    all_positions = comparison[
        comparison["position_scope"] == "all"
    ].copy()

    print("\n=== 期間別レジーム差（all positions） ===")
    columns = [
        "analysis_period",
        "target",
        "ref",
        "overall_average_pct",
        "high_minus_low_average_pct",
        "down_minus_up_average_pct",
    ]
    print(
        all_positions.sort_values(
            ["analysis_start_year", "target", "ref"]
        )[columns].to_string(index=False)
    )


def main(
    config_path=None,
    data_folder=None,
    save_dir=None,
):
    config_path = (
        Path(config_path)
        if config_path is not None
        else PROJECT_DIR / "config.toml"
    )
    save_dir = (
        Path(save_dir)
        if save_dir is not None
        else default_save_dir()
    )
    save_dir.mkdir(parents=True, exist_ok=True)

    config_data = load_config(config_path)
    config = BackTestConfig(config_data)
    regime_config = RegimeResearchConfig.from_config_data(
        config_data
    )

    validate_periods(config, regime_config)

    print("=== レジーム研究 ===")
    print(
        "戦略選抜期間: "
        f"{config.ranking_period[0]}～{config.ranking_period[1]}"
    )
    print("レジーム分析期間:")
    for period in regime_config.periods:
        role = period_role(period, config.ranking_period)
        print(
            f"  {period[0]}～{period[1]} "
            f"({role})"
        )
    print(
        "レジーム定義: "
        f"vol={regime_config.volatility_window}日, "
        f"vol基準={regime_config.volatility_baseline_window}日中央値, "
        f"方向={regime_config.direction_sma_window}日SMA"
    )
    print(
        "注意: entry日のレジームは前営業日までのTarget価格だけで判定します。"
    )

    tasks = build_candidate_tasks(
        config,
        regime_config,
    )
    print(f"選抜対象タスク数: {len(tasks)}")

    ref_cache, target_cache = build_task_caches(
        tasks,
        data_folder,
    )

    selection_rows = run_selection_tasks(
        config,
        tasks,
        ref_cache,
        target_cache,
    )
    selected_rows = select_best_per_pair(
        selection_rows,
        regime_config,
    )

    selected_frame = build_selected_strategy_frame(
        selected_rows
    )
    print_selected_strategies(
        selected_frame,
        config.ranking_period,
    )

    # run_one_shared を使った場合でも、このプロセス側で
    # selected task を再実行できるようキャッシュを設定する。
    backtest.init_worker(
        config,
        ref_cache,
        target_cache,
    )

    regime_frames = {}
    trade_frames = []
    summary_rows = []

    for task, selection_result in selected_rows:
        if task.target_name not in regime_frames:
            regime_frames[task.target_name] = build_regime_frame(
                task.target_name,
                regime_config,
                data_folder,
            )

        all_trades = run_selected_strategy(
            config,
            task,
        )

        for period in regime_config.periods:
            role = period_role(
                period,
                config.ranking_period,
            )
            trades = restrict_to_evaluation_period(
                all_trades,
                period,
            )
            trades = attach_regime(
                trades,
                regime_frames[task.target_name],
            )
            trades = add_strategy_columns(
                trades,
                task,
                selection_result,
                period,
                role,
            )

            trade_frames.append(trades)
            summary_rows.extend(
                summarize_trades(
                    trades,
                    task,
                    selection_result,
                    regime_config,
                    period,
                    role,
                )
            )

    trade_frame = (
        pd.concat(trade_frames, ignore_index=True)
        if trade_frames
        else pd.DataFrame()
    )
    summary_frame = pd.DataFrame(summary_rows)
    comparison_frame = build_comparison_frame(
        summary_frame
    )

    selected_path = save_dir / SELECTED_OUTPUT_FILE
    trade_path = save_dir / TRADE_OUTPUT_FILE
    summary_path = save_dir / SUMMARY_OUTPUT_FILE
    comparison_path = save_dir / COMPARISON_OUTPUT_FILE

    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    selected_frame.to_csv(
        selected_path,
        **csv_options,
    )
    trade_frame.to_csv(
        trade_path,
        **csv_options,
    )
    summary_frame.to_csv(
        summary_path,
        **csv_options,
    )
    comparison_frame.to_csv(
        comparison_path,
        **csv_options,
    )

    print_regime_highlights(comparison_frame)

    print("\n出力:")
    print(f"  {selected_path}")
    print(f"  {trade_path}")
    print(f"  {summary_path}")
    print(f"  {comparison_path}")
    print(
        "\nこの段階ではレジームを売買フィルタには使いません。"
        "まず成績差が再現するかを観察します。"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="既存シグナル戦略のレジーム別成績を研究する。"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="config.toml のパス",
    )
    parser.add_argument(
        "--data-folder",
        type=Path,
        default=None,
        help="市場データフォルダ",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="CSV出力先",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        config_path=args.config,
        data_folder=args.data_folder,
        save_dir=args.save_dir,
    )
