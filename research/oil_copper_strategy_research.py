import argparse
import math
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


RESEARCH_DIR = Path(__file__).resolve().parent
PROJECT_DIR = RESEARCH_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import backtest
from backtest_config import BackTestConfig
from market_data import MarketData
from strategy_task import StrategyTask


SELECTED_OUTPUT_FILE = (
    "oil_copper_selected_strategy.csv"
)
TRADE_OUTPUT_FILE = (
    "oil_copper_strategy_trades.csv"
)
SUMMARY_OUTPUT_FILE = (
    "oil_copper_strategy_summary.csv"
)

ROUND_DIGITS = 9

FROZEN_SELECTION_PERIOD = (2001, 2015)
FROZEN_EVALUATION_PERIOD = (2016, 2020)
FROZEN_TARGET = "OIL_USD"
FROZEN_REF = "COPPER_USD"
FROZEN_SELECTION_METRIC = "t_value"
FROZEN_USE_EXCESS_RETURN = False

# 現在のconfig.tomlにある既存OIL取引条件。
FROZEN_OIL_COST = 0.03
FROZEN_OIL_SWAP = 0.0


@dataclass(frozen=True)
class OilCopperResearchConfig:
    selection_period: tuple[int, int]
    evaluation_period: tuple[int, int]

    target: str
    ref: str

    selection_metric: str
    use_excess_return: bool

    @classmethod
    def from_config_data(
        cls,
        config_data: dict,
    ):
        raw = config_data.get(
            "oil_copper_strategy_research",
            {},
        )

        config = cls(
            selection_period=_parse_period(
                raw.get(
                    "selection_period",
                    FROZEN_SELECTION_PERIOD,
                ),
                "selection_period",
            ),
            evaluation_period=_parse_period(
                raw.get(
                    "evaluation_period",
                    FROZEN_EVALUATION_PERIOD,
                ),
                "evaluation_period",
            ),
            target=str(
                raw.get(
                    "target",
                    FROZEN_TARGET,
                )
            ),
            ref=str(
                raw.get(
                    "ref",
                    FROZEN_REF,
                )
            ),
            selection_metric=str(
                raw.get(
                    "selection_metric",
                    FROZEN_SELECTION_METRIC,
                )
            ),
            use_excess_return=bool(
                raw.get(
                    "use_excess_return",
                    FROZEN_USE_EXCESS_RETURN,
                )
            ),
        )

        config.validate_frozen()
        return config

    def validate_frozen(self):
        expected = {
            "selection_period": (
                FROZEN_SELECTION_PERIOD
            ),
            "evaluation_period": (
                FROZEN_EVALUATION_PERIOD
            ),
            "target": FROZEN_TARGET,
            "ref": FROZEN_REF,
            "selection_metric": (
                FROZEN_SELECTION_METRIC
            ),
            "use_excess_return": (
                FROZEN_USE_EXCESS_RETURN
            ),
        }

        for name, expected_value in expected.items():
            actual = getattr(self, name)
            if actual != expected_value:
                raise ValueError(
                    f"{name} は {expected_value!r} "
                    "に固定しています。"
                    f"実際: {actual!r}"
                )


def _parse_period(
    value,
    field_name: str,
) -> tuple[int, int]:
    if len(value) != 2:
        raise ValueError(
            f"{field_name} は "
            "[開始年, 終了年] にしてください。"
        )

    start_year = int(value[0])
    end_year = int(value[1])

    if start_year > end_year:
        raise ValueError(
            f"{field_name} は "
            "開始年 <= 終了年 にしてください。"
        )

    return start_year, end_year


def default_save_dir() -> Path:
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Dropbox"
            / "Private"
            / "trade_test_results"
        )
    return Path("./")


def load_config(
    config_path: Path,
) -> dict:
    try:
        with open(config_path, "rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"config.toml が見つかりません: "
            f"{config_path}"
        ) from None


def validate_backtest_environment(
    config: BackTestConfig,
    research_config: OilCopperResearchConfig,
):
    if tuple(config.ranking_period) != (
        research_config.selection_period
    ):
        raise ValueError(
            "ranking_period は [2001, 2015] "
            "に固定してください。"
        )

    if config.no_overlap is not True:
        raise ValueError(
            "no_overlap は true に固定してください。"
        )

    if config.use_excess_return != [False]:
        raise ValueError(
            "use_excess_return は [false] "
            "に固定してください。"
        )

    if config.filter_signal_type:
        raise ValueError(
            "filter_signal_type は空文字にしてください。"
        )

    if not math.isclose(
        float(config.extra_cost_pct),
        0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "extra_cost_pct は0に固定してください。"
        )

    oil_cost = config.cost_of(FROZEN_TARGET)
    if not math.isclose(
        oil_cost,
        FROZEN_OIL_COST,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "OIL_USD cost は0.03に固定しています。"
            f"実際: {oil_cost}"
        )

    oil_swap = config.swap_of(FROZEN_TARGET)
    if not math.isclose(
        oil_swap,
        FROZEN_OIL_SWAP,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "OIL_USD swap は0に固定しています。"
            f"実際: {oil_swap}"
        )


def build_candidate_tasks(
    config: BackTestConfig,
    research_config: OilCopperResearchConfig,
) -> list[StrategyTask]:
    """現在の通常探索空間を、そのままこの1ペアへ適用する。"""
    if research_config.ref not in config.symbols:
        raise ValueError(
            f"symbolsに {research_config.ref} "
            "がありません。"
        )
    if research_config.target not in config.symbols:
        raise ValueError(
            f"symbolsに {research_config.target} "
            "がありません。"
        )

    return [
        StrategyTask(
            ref_name=research_config.ref,
            target_name=research_config.target,
            signal_type=signal_type,
            counter_trade=counter_trade,
            use_excess_return=False,
            threshold_width=threshold_width,
            hold_days=hold_days,
            start_days=start_days,
            sma_period=sma_period,
        )
        for signal_type in config.signal_type_list
        for counter_trade in config.counter_trade
        for threshold_width in config.widths_of(
            signal_type
        )
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]


def trim_market_data_end_year(
    market_data: MarketData,
    end_year: int,
):
    """2021+をシグナル計算にも入れないため2020末で切る。"""
    market_data.df = market_data.df[
        market_data.df["日付"].dt.year
        <= end_year
    ].copy()


def build_task_caches(
    tasks: list[StrategyTask],
    end_year: int,
    data_folder=None,
):
    ref_cache = {}
    target_cache = {}
    market_data_cache = {}

    def get_market_data(name: str):
        if name not in market_data_cache:
            data = MarketData(
                name,
                data_folder,
            )
            trim_market_data_end_year(
                data,
                end_year,
            )
            market_data_cache[name] = data

        return market_data_cache[name]

    for task in tasks:
        ref_key = (
            task.ref_name,
            task.start_days,
            task.sma_period,
        )
        if ref_key not in ref_cache:
            ref_data = get_market_data(
                task.ref_name
            )
            ref_cache[ref_key] = (
                ref_data.calc_ref_signals(
                    task.start_days,
                    task.sma_period,
                )
            )

        target_key = (
            task.target_name,
            task.hold_days,
        )
        if target_key not in target_cache:
            target_data = get_market_data(
                task.target_name
            )
            target_cache[target_key] = (
                target_data.calc_target_prices(
                    task.hold_days
                )
            )

    return ref_cache, target_cache


def run_selection(
    config: BackTestConfig,
    tasks: list[StrategyTask],
    ref_cache,
    target_cache,
):
    """ranking_period=2001-2015の統計だけで候補を評価する。"""
    backtest.init_worker(
        config,
        ref_cache,
        target_cache,
    )

    rows = []

    for task in tasks:
        result = backtest.run_one(
            config,
            task,
        )
        if result is not None:
            rows.append(
                (task, result)
            )

    if not rows:
        raise ValueError(
            "2001-2015の選抜条件を満たす"
            "候補戦略がありません。"
        )

    rows.sort(
        key=lambda item: (
            -_finite_or_minus_inf(
                item[1].get(
                    FROZEN_SELECTION_METRIC
                )
            ),
            item[0],
        )
    )

    return rows[0], rows


def _finite_or_minus_inf(
    value,
) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float("-inf")

    return (
        value
        if math.isfinite(value)
        else float("-inf")
    )


def run_selected_strategy(
    config: BackTestConfig,
    task: StrategyTask,
    ref_cache,
    target_cache,
) -> pd.DataFrame:
    backtest.init_worker(
        config,
        ref_cache,
        target_cache,
    )

    trades, _, _ = backtest.calc_trade_results(
        config,
        False,
        *task.as_backtest_args(),
    )

    if trades is None:
        return pd.DataFrame()

    return trades.copy()


def restrict_completed_period(
    trades: pd.DataFrame,
    period: tuple[int, int],
) -> pd.DataFrame:
    start_year, end_year = period

    return trades[
        (trades["entry_year"] >= start_year)
        & (trades["exit_year"] <= end_year)
        & (~trades["is_open"])
        & trades["profit_pct"].notna()
    ].copy()


def summarize_values(
    values: pd.Series,
) -> dict:
    values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    count = len(values)
    if count == 0:
        return {
            "trade_count": 0,
            "average_pct": float("nan"),
            "median_pct": float("nan"),
            "win_rate": float("nan"),
            "std_pct": float("nan"),
            "t_value": float("nan"),
            "sum_pct": 0.0,
            "worst_trade_pct": float("nan"),
            "best_trade_pct": float("nan"),
        }

    average = float(values.mean())
    median = float(values.median())
    win_rate = float(
        (values > 0).mean() * 100.0
    )
    std = (
        float(values.std(ddof=1))
        if count > 1
        else float("nan")
    )

    t_value = (
        average / std * math.sqrt(count)
        if (
            count > 1
            and math.isfinite(std)
            and std > 0
        )
        else float("nan")
    )

    return {
        "trade_count": count,
        "average_pct": average,
        "median_pct": median,
        "win_rate": win_rate,
        "std_pct": std,
        "t_value": t_value,
        "sum_pct": float(values.sum()),
        "worst_trade_pct": float(values.min()),
        "best_trade_pct": float(values.max()),
    }


def build_selected_frame(
    task: StrategyTask,
    selection_result: dict,
) -> pd.DataFrame:
    row = {
        "target": task.target_name,
        "ref": task.ref_name,
        "signal_type": task.signal_type,
        "counter_trade": task.counter_trade,
        "use_excess_return": task.use_excess_return,
        "threshold_width": task.threshold_width,
        "hold_days": task.hold_days,
        "start_days": task.start_days,
        "sma_period": task.sma_period,
        "is_trade_count": selection_result.get(
            "trade_count"
        ),
        "is_average_pct": selection_result.get(
            "average_pct"
        ),
        "is_win_rate": selection_result.get(
            "win_rate"
        ),
        "is_t_value": selection_result.get(
            "t_value"
        ),
        "is_positive_year_ratio": (
            selection_result.get(
                "positive_year_ratio"
            )
        ),
        "is_worst_year_profit": (
            selection_result.get(
                "worst_year_profit"
            )
        ),
    }

    return pd.DataFrame([row])


def build_summary(
    trades: pd.DataFrame,
    research_config: OilCopperResearchConfig,
) -> pd.DataFrame:
    rows = []

    periods = [
        (
            "selection_2001_2015",
            research_config.selection_period,
        ),
        (
            "development_2016_2020",
            research_config.evaluation_period,
        ),
    ]

    for label, period in periods:
        period_trades = restrict_completed_period(
            trades,
            period,
        )

        for position in (
            "all",
            "long",
            "short",
        ):
            if position == "all":
                selected = period_trades
            else:
                selected = period_trades[
                    period_trades["position"]
                    == position
                ]

            row = {
                "period": label,
                "period_start_year": period[0],
                "period_end_year": period[1],
                "position": position,
            }
            row.update(
                summarize_values(
                    selected["profit_pct"]
                )
            )
            rows.append(row)

    return pd.DataFrame(rows)


def add_strategy_columns(
    trades: pd.DataFrame,
    task: StrategyTask,
) -> pd.DataFrame:
    result = trades.copy()

    fields = [
        ("target", task.target_name),
        ("ref", task.ref_name),
        ("signal_type", task.signal_type),
        (
            "counter_trade",
            task.counter_trade,
        ),
        (
            "use_excess_return",
            task.use_excess_return,
        ),
        (
            "threshold_width",
            task.threshold_width,
        ),
        ("hold_days", task.hold_days),
        ("start_days", task.start_days),
        ("sma_period", task.sma_period),
    ]

    for index, (name, value) in enumerate(
        fields
    ):
        result.insert(
            index,
            name,
            value,
        )

    return result


def print_result(
    selected_frame: pd.DataFrame,
    summary: pd.DataFrame,
    candidate_count: int,
):
    print(
        "\n=== Selected by 2001-2015 only ==="
    )
    print(
        selected_frame.to_string(
            index=False,
        )
    )

    print(
        f"\nEligible candidate count: "
        f"{candidate_count}"
    )

    print(
        "\n=== Fixed strategy result ==="
    )

    columns = [
        "period",
        "position",
        "trade_count",
        "average_pct",
        "median_pct",
        "win_rate",
        "t_value",
        "worst_trade_pct",
        "best_trade_pct",
    ]

    print(
        summary[columns].to_string(
            index=False,
        )
    )


def run(
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
    save_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    config_data = load_config(
        config_path
    )

    backtest_config = BackTestConfig(
        config_data
    )

    research_config = (
        OilCopperResearchConfig.from_config_data(
            config_data
        )
    )

    validate_backtest_environment(
        backtest_config,
        research_config,
    )

    tasks = build_candidate_tasks(
        backtest_config,
        research_config,
    )

    print(
        "=== OIL_USD <- COPPER_USD "
        "Strategy Research Step 1 ==="
    )
    print(
        "2021年以降は今回の計算対象に"
        "入れません。"
    )
    print(
        "Selection: 2001-2015 t_value only"
    )
    print(
        "Development: 2016-2020 fixed strategy"
    )
    print(
        f"Candidate tasks: {len(tasks)}"
    )

    (
        ref_cache,
        target_cache,
    ) = build_task_caches(
        tasks,
        research_config.evaluation_period[1],
        data_folder,
    )

    (
        selected_pair,
        selection_rows,
    ) = run_selection(
        backtest_config,
        tasks,
        ref_cache,
        target_cache,
    )

    selected_task, selection_result = (
        selected_pair
    )

    trades = run_selected_strategy(
        backtest_config,
        selected_task,
        ref_cache,
        target_cache,
    )

    if trades.empty:
        raise ValueError(
            "選抜戦略のトレードがありません。"
        )

    # 出力にも2021+を含めない。
    trades = trades[
        trades["entry_year"]
        <= research_config.evaluation_period[1]
    ].copy()

    trades = add_strategy_columns(
        trades,
        selected_task,
    )

    selected_frame = build_selected_frame(
        selected_task,
        selection_result,
    )

    summary = build_summary(
        trades,
        research_config,
    )

    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    selected_path = (
        save_dir / SELECTED_OUTPUT_FILE
    )
    trade_path = (
        save_dir / TRADE_OUTPUT_FILE
    )
    summary_path = (
        save_dir / SUMMARY_OUTPUT_FILE
    )

    selected_frame.to_csv(
        selected_path,
        **csv_options,
    )
    trades.to_csv(
        trade_path,
        **csv_options,
    )
    summary.to_csv(
        summary_path,
        **csv_options,
    )

    print_result(
        selected_frame,
        summary,
        len(selection_rows),
    )

    print("\n出力:")
    print(f"  {selected_path}")
    print(f"  {trade_path}")
    print(f"  {summary_path}")

    print(
        "\nこのStepでは2021-2025を見ません。"
        "2016-2020の結果を確認してから、"
        "次の条件を固定します。"
    )

    return (
        selected_path,
        trade_path,
        summary_path,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "OIL_USD <- COPPER_USDを"
            "2001-2015だけで選抜し、"
            "2016-2020へ固定適用する。"
        )
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

    run(
        config_path=args.config,
        data_folder=args.data_folder,
        save_dir=args.save_dir,
    )
