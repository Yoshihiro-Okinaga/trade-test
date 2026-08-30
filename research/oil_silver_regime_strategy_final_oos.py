import argparse
import math
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
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


TRADE_OUTPUT_FILE = (
    "oil_silver_regime_final_oos_trades.csv"
)
SUMMARY_OUTPUT_FILE = (
    "oil_silver_regime_final_oos_summary.csv"
)
VERDICT_OUTPUT_FILE = (
    "oil_silver_regime_final_oos_verdict.csv"
)
ROUND_DIGITS = 9

# ---------------------------------------------------------
# 2021-2025を見る前に固定した最終OOS条件。
# config.toml が1つでも異なれば実行を止める。
# ---------------------------------------------------------
FROZEN_PERIOD = (2021, 2025)
FROZEN_TARGET = "OIL_USD"
FROZEN_REF = "SILVER_USD"

FROZEN_SIGNAL_TYPE = SignalType.CHANGE
FROZEN_COUNTER_TRADE = False
FROZEN_USE_EXCESS_RETURN = False
FROZEN_THRESHOLD_WIDTH = 1.0
FROZEN_HOLD_DAYS = 20
FROZEN_START_DAYS = 1
FROZEN_SMA_PERIOD = 100

FROZEN_DIRECTION_SMA_WINDOW = 200
FROZEN_FILTER_DIRECTION = "down"

# 既存backtest側のOILコスト。
FROZEN_OIL_COST = 0.03
FROZEN_OIL_SWAP = 0.0

# baselineに追加する保守的なstress friction。
FROZEN_STRESS_EXTRA_COST_PCT = 0.5

# 事前固定した判定条件。
FROZEN_MIN_CLOSED_TRADES = 15
FROZEN_MIN_BASELINE_AVERAGE_PCT = 0.0
FROZEN_MIN_BASELINE_MEDIAN_PCT = 0.0
FROZEN_MIN_BASELINE_WIN_RATE = 50.0
FROZEN_REQUIRE_DOWN_BETTER_THAN_UP = True


@dataclass(frozen=True)
class FinalOosConfig:
    period: tuple[int, int]

    target: str
    ref: str

    signal_type: SignalType
    counter_trade: bool
    use_excess_return: bool
    threshold_width: float
    hold_days: int
    start_days: int
    sma_period: int

    direction_sma_window: int
    filter_direction: str

    stress_extra_cost_pct: float

    min_closed_trades: int
    min_baseline_average_pct: float
    min_baseline_median_pct: float
    min_baseline_win_rate: float
    require_down_better_than_up: bool

    @classmethod
    def from_config_data(
        cls,
        config_data: dict,
    ):
        raw = config_data.get(
            "oil_silver_regime_strategy_final_oos",
            {},
        )

        try:
            signal_type = SignalType(
                raw.get(
                    "signal_type",
                    FROZEN_SIGNAL_TYPE,
                )
            )
        except ValueError as exc:
            raise ValueError(
                "oil_silver_regime_strategy_final_oos."
                "signal_type が不正です。"
            ) from exc

        config = cls(
            period=_parse_period(
                raw.get(
                    "period",
                    FROZEN_PERIOD,
                ),
                "oil_silver_regime_strategy_final_oos.period",
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
            signal_type=signal_type,
            counter_trade=bool(
                raw.get(
                    "counter_trade",
                    FROZEN_COUNTER_TRADE,
                )
            ),
            use_excess_return=bool(
                raw.get(
                    "use_excess_return",
                    FROZEN_USE_EXCESS_RETURN,
                )
            ),
            threshold_width=float(
                raw.get(
                    "threshold_width",
                    FROZEN_THRESHOLD_WIDTH,
                )
            ),
            hold_days=int(
                raw.get(
                    "hold_days",
                    FROZEN_HOLD_DAYS,
                )
            ),
            start_days=int(
                raw.get(
                    "start_days",
                    FROZEN_START_DAYS,
                )
            ),
            sma_period=int(
                raw.get(
                    "sma_period",
                    FROZEN_SMA_PERIOD,
                )
            ),
            direction_sma_window=int(
                raw.get(
                    "direction_sma_window",
                    FROZEN_DIRECTION_SMA_WINDOW,
                )
            ),
            filter_direction=str(
                raw.get(
                    "filter_direction",
                    FROZEN_FILTER_DIRECTION,
                )
            ),
            stress_extra_cost_pct=float(
                raw.get(
                    "stress_extra_cost_pct",
                    FROZEN_STRESS_EXTRA_COST_PCT,
                )
            ),
            min_closed_trades=int(
                raw.get(
                    "min_closed_trades",
                    FROZEN_MIN_CLOSED_TRADES,
                )
            ),
            min_baseline_average_pct=float(
                raw.get(
                    "min_baseline_average_pct",
                    FROZEN_MIN_BASELINE_AVERAGE_PCT,
                )
            ),
            min_baseline_median_pct=float(
                raw.get(
                    "min_baseline_median_pct",
                    FROZEN_MIN_BASELINE_MEDIAN_PCT,
                )
            ),
            min_baseline_win_rate=float(
                raw.get(
                    "min_baseline_win_rate",
                    FROZEN_MIN_BASELINE_WIN_RATE,
                )
            ),
            require_down_better_than_up=bool(
                raw.get(
                    "require_down_better_than_up",
                    FROZEN_REQUIRE_DOWN_BETTER_THAN_UP,
                )
            ),
        )

        config.validate_frozen()
        return config

    def validate_frozen(self):
        expected = {
            "period": FROZEN_PERIOD,
            "target": FROZEN_TARGET,
            "ref": FROZEN_REF,
            "signal_type": FROZEN_SIGNAL_TYPE,
            "counter_trade": FROZEN_COUNTER_TRADE,
            "use_excess_return": (
                FROZEN_USE_EXCESS_RETURN
            ),
            "threshold_width": (
                FROZEN_THRESHOLD_WIDTH
            ),
            "hold_days": FROZEN_HOLD_DAYS,
            "start_days": FROZEN_START_DAYS,
            "sma_period": FROZEN_SMA_PERIOD,
            "direction_sma_window": (
                FROZEN_DIRECTION_SMA_WINDOW
            ),
            "filter_direction": (
                FROZEN_FILTER_DIRECTION
            ),
            "stress_extra_cost_pct": (
                FROZEN_STRESS_EXTRA_COST_PCT
            ),
            "min_closed_trades": (
                FROZEN_MIN_CLOSED_TRADES
            ),
            "min_baseline_average_pct": (
                FROZEN_MIN_BASELINE_AVERAGE_PCT
            ),
            "min_baseline_median_pct": (
                FROZEN_MIN_BASELINE_MEDIAN_PCT
            ),
            "min_baseline_win_rate": (
                FROZEN_MIN_BASELINE_WIN_RATE
            ),
            "require_down_better_than_up": (
                FROZEN_REQUIRE_DOWN_BETTER_THAN_UP
            ),
        }

        for name, expected_value in expected.items():
            actual = getattr(self, name)
            if actual != expected_value:
                raise ValueError(
                    f"最終OOSの {name} は "
                    f"{expected_value!r} "
                    "に固定しています。"
                    f"実際: {actual!r}"
                )

    def to_task(self) -> StrategyTask:
        return StrategyTask(
            ref_name=self.ref,
            target_name=self.target,
            signal_type=self.signal_type,
            counter_trade=self.counter_trade,
            use_excess_return=(
                self.use_excess_return
            ),
            threshold_width=self.threshold_width,
            hold_days=self.hold_days,
            start_days=self.start_days,
            sma_period=self.sma_period,
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
            "filter_signal_type は空文字に固定してください。"
        )

    if not math.isclose(
        float(config.extra_cost_pct),
        0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "本体extra_cost_pctは0に固定してください。"
            "stressは専用列で計算します。"
        )

    if config.trade_code_type != TradeCodeType.ALL:
        raise ValueError(
            "trade_code_type は all に固定してください。"
        )

    if not math.isclose(
        config.center_of(FROZEN_SIGNAL_TYPE),
        0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "SMAのthreshold_centerは0に固定しています。"
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


def trim_market_data_end_year(
    market_data: MarketData,
    end_year: int,
):
    """2026年以降を最終OOS計算へ入れない。"""
    market_data.df = market_data.df[
        market_data.df["日付"].dt.year <= end_year
    ].copy()


def build_task_caches(
    task: StrategyTask,
    end_year: int,
    data_folder=None,
):
    ref_data = MarketData(
        task.ref_name,
        data_folder,
    )
    target_data = MarketData(
        task.target_name,
        data_folder,
    )

    trim_market_data_end_year(
        ref_data,
        end_year,
    )
    trim_market_data_end_year(
        target_data,
        end_year,
    )

    ref_cache = {
        (
            task.ref_name,
            task.start_days,
            task.sma_period,
        ): ref_data.calc_ref_signals(
            task.start_days,
            task.sma_period,
        )
    }

    target_cache = {
        (
            task.target_name,
            task.hold_days,
        ): target_data.calc_target_prices(
            task.hold_days
        )
    }

    target_prices = target_data.df[
        ["日付", "終値"]
    ].copy()

    return (
        ref_cache,
        target_cache,
        target_prices,
    )


def build_direction_frame(
    target_prices: pd.DataFrame,
    sma_window: int,
) -> pd.DataFrame:
    """entry日の前営業日までの情報だけでup/downを作る。"""
    data = target_prices.copy()

    close = pd.to_numeric(
        data["終値"],
        errors="coerce",
    )

    direction_sma = close.rolling(
        sma_window,
        min_periods=sma_window,
    ).mean()

    known_close = close.shift(1)
    known_sma = direction_sma.shift(1)

    invalid = (
        known_close.isna()
        | known_sma.isna()
    )

    data["regime_direction"] = np.where(
        invalid,
        None,
        np.where(
            known_close >= known_sma,
            "up",
            "down",
        ),
    )

    data["known_close"] = known_close
    data["known_direction_sma"] = known_sma
    data["known_price_vs_sma_pct"] = (
        (known_close - known_sma)
        / known_sma
        * 100.0
    )

    return data[[
        "日付",
        "regime_direction",
        "known_close",
        "known_direction_sma",
        "known_price_vs_sma_pct",
    ]]


def run_strategy(
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


def attach_direction(
    trades: pd.DataFrame,
    direction_frame: pd.DataFrame,
) -> pd.DataFrame:
    return trades.merge(
        direction_frame,
        left_on="entry_date",
        right_on="日付",
        how="left",
    ).drop(columns=["日付"])


def restrict_period(
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


def build_summary(
    trades: pd.DataFrame,
    config: FinalOosConfig,
) -> pd.DataFrame:
    rows = []

    for regime in ("all", "down", "up"):
        if regime == "all":
            selected = trades
        else:
            selected = trades[
                trades["regime_direction"]
                == regime
            ]

        baseline = summarize_values(
            selected["profit_pct"]
        )

        stress_values = (
            selected["profit_pct"]
            - config.stress_extra_cost_pct
        )
        stress = summarize_values(
            stress_values
        )

        row = {
            "regime_direction": regime,
            "stress_extra_cost_pct": (
                config.stress_extra_cost_pct
            ),
        }

        for name, value in baseline.items():
            row[f"baseline_{name}"] = value

        for name, value in stress.items():
            row[f"stress_{name}"] = value

        rows.append(row)

    return pd.DataFrame(rows)


def one_summary_row(
    summary: pd.DataFrame,
    regime: str,
) -> pd.Series:
    rows = summary[
        summary["regime_direction"] == regime
    ]

    if len(rows) != 1:
        raise ValueError(
            f"summaryの {regime} 行を "
            "一意に取得できません。"
        )

    return rows.iloc[0]


def build_verdict(
    summary: pd.DataFrame,
    config: FinalOosConfig,
) -> pd.DataFrame:
    down = one_summary_row(
        summary,
        "down",
    )
    up = one_summary_row(
        summary,
        "up",
    )

    checks = {
        "enough_trades": (
            down["baseline_trade_count"]
            >= config.min_closed_trades
        ),
        "baseline_average_positive": (
            down["baseline_average_pct"]
            > config.min_baseline_average_pct
        ),
        "baseline_median_positive": (
            down["baseline_median_pct"]
            > config.min_baseline_median_pct
        ),
        "baseline_win_rate_ok": (
            down["baseline_win_rate"]
            >= config.min_baseline_win_rate
        ),
        "stress_average_positive": (
            down["stress_average_pct"] > 0
        ),
        "down_better_than_up": (
            down["baseline_average_pct"]
            > up["baseline_average_pct"]
        ),
    }

    if not checks["enough_trades"]:
        verdict = "INCONCLUSIVE_TOO_FEW_TRADES"
    elif not checks["baseline_average_positive"]:
        verdict = "FAIL"
    elif all(checks.values()):
        verdict = "STRONG_PASS"
    elif (
        checks["stress_average_positive"]
        and checks["baseline_median_positive"]
        and checks["baseline_win_rate_ok"]
        and not checks["down_better_than_up"]
    ):
        verdict = "STRATEGY_PASS_REGIME_FAIL"
    else:
        verdict = "WEAK_PASS"

    row = {
        "verdict": verdict,
        "period_start_year": config.period[0],
        "period_end_year": config.period[1],
        "down_trade_count": (
            down["baseline_trade_count"]
        ),
        "down_baseline_average_pct": (
            down["baseline_average_pct"]
        ),
        "down_baseline_median_pct": (
            down["baseline_median_pct"]
        ),
        "down_baseline_win_rate": (
            down["baseline_win_rate"]
        ),
        "down_baseline_t_value": (
            down["baseline_t_value"]
        ),
        "down_stress_average_pct": (
            down["stress_average_pct"]
        ),
        "up_baseline_average_pct": (
            up["baseline_average_pct"]
        ),
        "down_minus_up_average_pct": (
            down["baseline_average_pct"]
            - up["baseline_average_pct"]
        ),
        "stress_extra_cost_pct": (
            config.stress_extra_cost_pct
        ),
    }

    row.update(checks)

    return pd.DataFrame([row])


def add_output_columns(
    trades: pd.DataFrame,
    config: FinalOosConfig,
) -> pd.DataFrame:
    result = trades.copy()

    result["passes_regime_filter"] = (
        result["regime_direction"]
        == config.filter_direction
    )
    result["stress_profit_pct"] = (
        result["profit_pct"]
        - config.stress_extra_cost_pct
    )

    return result


def print_result(
    summary: pd.DataFrame,
    verdict: pd.DataFrame,
):
    columns = [
        "regime_direction",
        "baseline_trade_count",
        "baseline_average_pct",
        "baseline_median_pct",
        "baseline_win_rate",
        "baseline_t_value",
        "stress_average_pct",
    ]

    print(
        "\n=== FINAL OOS Summary ==="
    )
    print(
        summary[columns].to_string(
            index=False,
        )
    )

    print(
        "\n=== Pre-frozen Verdict ==="
    )
    print(
        verdict.to_string(
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
    final_config = (
        FinalOosConfig.from_config_data(
            config_data
        )
    )

    validate_backtest_environment(
        backtest_config
    )

    task = final_config.to_task()

    print(
        "=== OIL <- GOLD × OIL down "
        "FINAL OOS ==="
    )
    print(
        "2021-2025を一度だけ評価します。"
    )
    print(
        "2026年以降は今回の計算対象に入れません。"
    )
    print(
        "Fixed strategy: "
        "change / threshold=1 / counter=false / "
        "hold=20 / start=1 / SMA=100"
    )
    print(
        "Fixed regime: "
        "OIL前営業日終値 < 前営業日200日SMA"
    )
    print(
        "Baseline OIL cost: 0.03 price units"
    )
    print(
        "Stress: baseline損益から "
        f"追加 {final_config.stress_extra_cost_pct}% "
        "/ trade"
    )

    (
        ref_cache,
        target_cache,
        target_prices,
    ) = build_task_caches(
        task,
        final_config.period[1],
        data_folder,
    )

    trades = run_strategy(
        backtest_config,
        task,
        ref_cache,
        target_cache,
    )
    if trades.empty:
        raise ValueError(
            "OIL <- GOLD のトレードがありません。"
        )

    direction_frame = build_direction_frame(
        target_prices,
        final_config.direction_sma_window,
    )
    trades = attach_direction(
        trades,
        direction_frame,
    )

    trades = restrict_period(
        trades,
        final_config.period,
    )
    trades = add_output_columns(
        trades,
        final_config,
    )

    summary = build_summary(
        trades,
        final_config,
    )
    verdict = build_verdict(
        summary,
        final_config,
    )

    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    trade_path = (
        save_dir / TRADE_OUTPUT_FILE
    )
    summary_path = (
        save_dir / SUMMARY_OUTPUT_FILE
    )
    verdict_path = (
        save_dir / VERDICT_OUTPUT_FILE
    )

    trades.to_csv(
        trade_path,
        **csv_options,
    )
    summary.to_csv(
        summary_path,
        **csv_options,
    )
    verdict.to_csv(
        verdict_path,
        **csv_options,
    )

    print_result(
        summary,
        verdict,
    )

    print("\n出力:")
    print(f"  {trade_path}")
    print(f"  {summary_path}")
    print(f"  {verdict_path}")
    print(
        "\nこの結果を見た後、"
        "同じ2021-2025で条件を調整して"
        "final OOSをやり直しません。"
    )

    return (
        trade_path,
        summary_path,
        verdict_path,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "OIL_USD <- SILVER_USD × OIL down "
            "の2021-2025 FINAL OOS。"
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
