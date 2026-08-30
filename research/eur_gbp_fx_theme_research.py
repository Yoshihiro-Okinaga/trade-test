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
from backtest_config import (
    BackTestConfig,
    SignalType,
    TradeCodeType,
)
from market_data import MarketData
from strategy_task import StrategyTask


STRATEGY_OUTPUT_FILE = (
    "eur_gbp_fx_theme_strategies.csv"
)
TRADE_OUTPUT_FILE = (
    "eur_gbp_fx_theme_trades.csv"
)
SUMMARY_OUTPUT_FILE = (
    "eur_gbp_fx_theme_summary.csv"
)
BREADTH_OUTPUT_FILE = (
    "eur_gbp_fx_theme_breadth.csv"
)

ROUND_DIGITS = 9

# EUR_GBP情報源テーマとして事前に記録されていた5 Target。
FROZEN_PERIODS = (
    (2001, 2005),
    (2006, 2010),
    (2011, 2015),
    (2016, 2020),
)
FROZEN_REF = "EUR_GBP"
FROZEN_TARGETS = (
    "GBP_USD",
    "AUD_USD",
    "AUD_JPY",
    "NZD_USD",
    "EUR_USD",
)

# 2001-2015だけで選ばれた代表StrategyTask。
# 今回は再選抜せず、この5本をそのまま使う。
FROZEN_TASKS = (
    (
        "GBP_USD",
        SignalType.DI,
        False,
        20.0,
        20,
        1,
        10,
    ),
    (
        "AUD_USD",
        SignalType.DI,
        False,
        20.0,
        20,
        1,
        10,
    ),
    (
        "AUD_JPY",
        SignalType.SMA,
        False,
        1.0,
        20,
        1,
        15,
    ),
    (
        "NZD_USD",
        SignalType.DI,
        False,
        20.0,
        20,
        1,
        10,
    ),
    (
        "EUR_USD",
        SignalType.DI,
        False,
        20.0,
        20,
        1,
        10,
    ),
)

# 選抜時の2001-2015統計。再選抜しないことを明示するため出力する。
FROZEN_IS_STATS = {
    "GBP_USD": {
        "trade_count": 184,
        "average_pct": 0.508692443,
        "win_rate": 60.326086957,
        "t_value": 3.111508759,
        "positive_year_ratio": 93.333333333,
    },
    "AUD_USD": {
        "trade_count": 184,
        "average_pct": 0.768467805,
        "win_rate": 54.891304348,
        "t_value": 3.076483024,
        "positive_year_ratio": 100.0,
    },
    "AUD_JPY": {
        "trade_count": 172,
        "average_pct": 0.908856306,
        "win_rate": 55.232558140,
        "t_value": 2.715070972,
        "positive_year_ratio": 80.0,
    },
    "NZD_USD": {
        "trade_count": 184,
        "average_pct": 0.693125665,
        "win_rate": 54.347826087,
        "t_value": 2.614362106,
        "positive_year_ratio": 86.666666667,
    },
    "EUR_USD": {
        "trade_count": 184,
        "average_pct": 0.457548409,
        "win_rate": 57.065217391,
        "t_value": 2.340003286,
        "positive_year_ratio": 86.666666667,
    },
}

# 現在のconfigで使っているTarget側cost / swap。
# 研究途中の設定変更で結果が変わらないよう固定して確認する。
FROZEN_TARGET_COST_SWAP = {
    "GBP_USD": (0.0001, -0.00009),
    "AUD_USD": (0.00004, 0.00117),
    "AUD_JPY": (0.005, 0.00891),
    "NZD_USD": (0.00016, -0.00291),
    "EUR_USD": (0.00003, -0.00319),
}


@dataclass(frozen=True)
class EurGbpFxThemeConfig:
    periods: tuple[tuple[int, int], ...]
    ref: str
    targets: tuple[str, ...]

    @classmethod
    def from_config_data(
        cls,
        config_data: dict,
    ):
        raw = config_data.get(
            "eur_gbp_fx_theme_research",
            {},
        )

        periods = tuple(
            _parse_period(
                value,
                "periods",
            )
            for value in raw.get(
                "periods",
                FROZEN_PERIODS,
            )
        )

        config = cls(
            periods=periods,
            ref=str(
                raw.get(
                    "ref",
                    FROZEN_REF,
                )
            ),
            targets=tuple(
                str(value)
                for value in raw.get(
                    "targets",
                    FROZEN_TARGETS,
                )
            ),
        )
        config.validate_frozen()
        return config

    def validate_frozen(self):
        expected = {
            "periods": FROZEN_PERIODS,
            "ref": FROZEN_REF,
            "targets": FROZEN_TARGETS,
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
):
    if tuple(config.ranking_period) != (2001, 2015):
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

    if config.trade_code_type != TradeCodeType.ALL:
        raise ValueError(
            "trade_code_type は all に固定してください。"
        )

    for target, (
        expected_cost,
        expected_swap,
    ) in FROZEN_TARGET_COST_SWAP.items():
        actual_cost = config.cost_of(target)
        actual_swap = config.swap_of(target)

        if not math.isclose(
            actual_cost,
            expected_cost,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"{target} cost は "
                f"{expected_cost} に固定しています。"
                f"実際: {actual_cost}"
            )

        if not math.isclose(
            actual_swap,
            expected_swap,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"{target} swap は "
                f"{expected_swap} に固定しています。"
                f"実際: {actual_swap}"
            )


def build_fixed_tasks() -> list[StrategyTask]:
    tasks = []

    for (
        target,
        signal_type,
        counter_trade,
        threshold_width,
        hold_days,
        start_days,
        sma_period,
    ) in FROZEN_TASKS:
        tasks.append(
            StrategyTask(
                ref_name=FROZEN_REF,
                target_name=target,
                signal_type=signal_type,
                counter_trade=counter_trade,
                use_excess_return=False,
                threshold_width=threshold_width,
                hold_days=hold_days,
                start_days=start_days,
                sma_period=sma_period,
            )
        )

    return tasks


def trim_market_data_end_year(
    market_data: MarketData,
    end_year: int,
):
    """2021+をシグナル計算にも渡さないため、2020末で切る。"""
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


def run_fixed_tasks(
    config: BackTestConfig,
    tasks: list[StrategyTask],
    ref_cache,
    target_cache,
) -> pd.DataFrame:
    backtest.init_worker(
        config,
        ref_cache,
        target_cache,
    )

    frames = []

    for task in tasks:
        trades, _, _ = backtest.calc_trade_results(
            config,
            False,
            *task.as_backtest_args(),
        )

        if trades is None or trades.empty:
            continue

        frame = trades.copy()

        # pandas 3系ではconcat時にDataFrame.attrsも比較される。
        # backtest由来のattrsにDataFrame等が含まれる場合、
        # attrs同士の比較でbool化できず例外になるため、
        # 結合前に付加メタデータだけを破棄する。
        # 売買結果の列・index・値には影響しない。
        frame.attrs.clear()

        fields = [
            ("target", task.target_name),
            ("ref", task.ref_name),
            ("signal_type", task.signal_type),
            ("counter_trade", task.counter_trade),
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
            frame.insert(
                index,
                name,
                value,
            )

        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        ignore_index=True,
    )


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


def build_strategy_frame(
    config: BackTestConfig,
    tasks: list[StrategyTask],
) -> pd.DataFrame:
    rows = []

    for task in tasks:
        is_stats = FROZEN_IS_STATS[
            task.target_name
        ]

        rows.append({
            "target": task.target_name,
            "ref": task.ref_name,
            "signal_type": task.signal_type,
            "counter_trade": task.counter_trade,
            "use_excess_return": (
                task.use_excess_return
            ),
            "threshold_width": (
                task.threshold_width
            ),
            "hold_days": task.hold_days,
            "start_days": task.start_days,
            "sma_period": task.sma_period,
            "target_cost": config.cost_of(
                task.target_name
            ),
            "target_swap": config.swap_of(
                task.target_name
            ),
            "is_trade_count": (
                is_stats["trade_count"]
            ),
            "is_average_pct": (
                is_stats["average_pct"]
            ),
            "is_win_rate": (
                is_stats["win_rate"]
            ),
            "is_t_value": (
                is_stats["t_value"]
            ),
            "is_positive_year_ratio": (
                is_stats[
                    "positive_year_ratio"
                ]
            ),
        })

    return pd.DataFrame(rows)


def build_summary(
    trades: pd.DataFrame,
    config: EurGbpFxThemeConfig,
) -> pd.DataFrame:
    rows = []

    for period in config.periods:
        period_name = (
            f"{period[0]}_{period[1]}"
        )

        for target in config.targets:
            target_trades = trades[
                trades["target"] == target
            ]
            target_trades = (
                restrict_completed_period(
                    target_trades,
                    period,
                )
            )

            for position in (
                "all",
                "long",
                "short",
            ):
                if position == "all":
                    selected = target_trades
                else:
                    selected = target_trades[
                        target_trades["position"]
                        == position
                    ]

                row = {
                    "analysis_period": period_name,
                    "analysis_start_year": (
                        period[0]
                    ),
                    "analysis_end_year": (
                        period[1]
                    ),
                    "period_role": (
                        "development"
                        if period == (2016, 2020)
                        else "selection_subperiod"
                    ),
                    "target": target,
                    "ref": FROZEN_REF,
                    "position": position,
                }
                row.update(
                    summarize_values(
                        selected["profit_pct"]
                    )
                )
                rows.append(row)

    return pd.DataFrame(rows)


def build_breadth(
    summary: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    all_rows = summary[
        summary["position"] == "all"
    ]

    for (
        period_name,
        period_frame,
    ) in all_rows.groupby(
        "analysis_period",
        sort=False,
    ):
        average_values = (
            period_frame["average_pct"]
        )

        rows.append({
            "analysis_period": period_name,
            "analysis_start_year": int(
                period_frame[
                    "analysis_start_year"
                ].iloc[0]
            ),
            "analysis_end_year": int(
                period_frame[
                    "analysis_end_year"
                ].iloc[0]
            ),
            "period_role": (
                period_frame[
                    "period_role"
                ].iloc[0]
            ),
            "target_count": len(
                period_frame
            ),
            "positive_average_target_count": int(
                (
                    period_frame[
                        "average_pct"
                    ] > 0
                ).sum()
            ),
            "positive_median_target_count": int(
                (
                    period_frame[
                        "median_pct"
                    ] > 0
                ).sum()
            ),
            "win_rate_ge_50_target_count": int(
                (
                    period_frame[
                        "win_rate"
                    ] >= 50.0
                ).sum()
            ),
            # trade件数で重みを付けず、
            # 5 Targetを同じ1票として扱う。
            "equal_target_average_pct": float(
                average_values.mean()
            ),
            "median_target_average_pct": float(
                average_values.median()
            ),
            "worst_target_average_pct": float(
                average_values.min()
            ),
            "best_target_average_pct": float(
                average_values.max()
            ),
            "all_target_average_positive": bool(
                (
                    average_values > 0
                ).all()
            ),
        })

    return pd.DataFrame(rows)


def print_result(
    strategies: pd.DataFrame,
    summary: pd.DataFrame,
    breadth: pd.DataFrame,
):
    print(
        "\n=== Frozen strategies "
        "(selected by 2001-2015 only) ==="
    )
    print(
        strategies[
            [
                "target",
                "signal_type",
                "threshold_width",
                "sma_period",
                "is_trade_count",
                "is_average_pct",
                "is_t_value",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\n=== Target results ==="
    )
    target_rows = summary[
        summary["position"] == "all"
    ]
    print(
        target_rows[
            [
                "analysis_period",
                "target",
                "trade_count",
                "average_pct",
                "median_pct",
                "win_rate",
                "t_value",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\n=== EUR_GBP source-theme breadth ==="
    )
    print(
        breadth.to_string(
            index=False
        )
    )

    print(
        "\n注意: これはportfolio成績ではありません。"
        "同じRefの情報が複数Targetへ広がるかを"
        "Target単位で確認する研究です。"
    )
    print(
        "2021-2025は今回の計算対象に入れていません。"
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
    theme_config = (
        EurGbpFxThemeConfig.from_config_data(
            config_data
        )
    )

    validate_backtest_environment(
        backtest_config
    )

    tasks = build_fixed_tasks()

    print(
        "=== EUR_GBP -> Multiple FX "
        "Source Theme Step 1 ==="
    )
    print(
        "5 Targetを事後選別せず全部使います。"
    )
    print(
        "2021年以降はシグナル計算にも"
        "入れません。"
    )

    end_year = max(
        period[1]
        for period in theme_config.periods
    )
    (
        ref_cache,
        target_cache,
    ) = build_task_caches(
        tasks,
        end_year,
        data_folder,
    )

    trades = run_fixed_tasks(
        backtest_config,
        tasks,
        ref_cache,
        target_cache,
    )

    if trades.empty:
        raise ValueError(
            "固定5戦略のトレードがありません。"
        )

    # 出力にも2021+を含めない。
    trades = trades[
        trades["entry_year"] <= end_year
    ].copy()

    strategies = build_strategy_frame(
        backtest_config,
        tasks,
    )
    summary = build_summary(
        trades,
        theme_config,
    )
    breadth = build_breadth(
        summary
    )

    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    strategy_path = (
        save_dir / STRATEGY_OUTPUT_FILE
    )
    trade_path = (
        save_dir / TRADE_OUTPUT_FILE
    )
    summary_path = (
        save_dir / SUMMARY_OUTPUT_FILE
    )
    breadth_path = (
        save_dir / BREADTH_OUTPUT_FILE
    )

    strategies.to_csv(
        strategy_path,
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
    breadth.to_csv(
        breadth_path,
        **csv_options,
    )

    print_result(
        strategies,
        summary,
        breadth,
    )

    print("\n出力:")
    print(f"  {strategy_path}")
    print(f"  {trade_path}")
    print(f"  {summary_path}")
    print(f"  {breadth_path}")

    return (
        strategy_path,
        trade_path,
        summary_path,
        breadth_path,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "EUR_GBPを共通Refとする5 FX Targetの"
            "横断的な先行情報テーマを検証する。"
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
