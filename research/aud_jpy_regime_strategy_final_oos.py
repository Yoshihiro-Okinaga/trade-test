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
    "aud_jpy_regime_final_oos_trades.csv"
)
SUMMARY_OUTPUT_FILE = (
    "aud_jpy_regime_final_oos_summary.csv"
)
VERDICT_OUTPUT_FILE = (
    "aud_jpy_regime_final_oos_verdict.csv"
)
ROUND_DIGITS = 9

# ---------------------------------------------------------
# 2021-2025を見る前に固定した最終OOS条件。
# config.toml が1つでも異なれば実行を止める。
# ---------------------------------------------------------
FROZEN_PERIOD = (2021, 2025)

FROZEN_TARGET = "AUD_JPY"
FROZEN_REF = "EUR_GBP"

FROZEN_SIGNAL_TYPE = SignalType.SMA
FROZEN_COUNTER_TRADE = False
FROZEN_USE_EXCESS_RETURN = False
FROZEN_THRESHOLD_WIDTH = 1.0
FROZEN_HOLD_DAYS = 20
FROZEN_START_DAYS = 1
FROZEN_SMA_PERIOD = 15

FROZEN_DIRECTION_SMA_WINDOW = 200
FROZEN_FILTER_DIRECTION = "up"

FROZEN_AUD_JPY_COST = 0.005
FROZEN_AUD_JPY_SWAP = 0.00891

FROZEN_STRESS_EXTRA_COST_PCT = 0.5

FROZEN_MIN_CLOSED_TRADES = 15
FROZEN_MIN_CONFIGURED_AVERAGE_PCT = 0.0
FROZEN_MIN_NEUTRAL_AVERAGE_PCT = 0.0
FROZEN_MIN_NEUTRAL_MEDIAN_PCT = 0.0
FROZEN_MIN_NEUTRAL_WIN_RATE = 50.0
FROZEN_REQUIRE_UP_BETTER_THAN_DOWN = True


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
    min_configured_average_pct: float
    min_neutral_average_pct: float
    min_neutral_median_pct: float
    min_neutral_win_rate: float
    require_up_better_than_down: bool

    @classmethod
    def from_config_data(
        cls,
        config_data: dict,
    ):
        raw = config_data.get(
            "aud_jpy_regime_strategy_final_oos",
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
                "aud_jpy_regime_strategy_final_oos."
                "signal_type が不正です。"
            ) from exc

        config = cls(
            period=_parse_period(
                raw.get(
                    "period",
                    FROZEN_PERIOD,
                ),
                "aud_jpy_regime_strategy_final_oos.period",
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
            min_configured_average_pct=float(
                raw.get(
                    "min_configured_average_pct",
                    FROZEN_MIN_CONFIGURED_AVERAGE_PCT,
                )
            ),
            min_neutral_average_pct=float(
                raw.get(
                    "min_neutral_average_pct",
                    FROZEN_MIN_NEUTRAL_AVERAGE_PCT,
                )
            ),
            min_neutral_median_pct=float(
                raw.get(
                    "min_neutral_median_pct",
                    FROZEN_MIN_NEUTRAL_MEDIAN_PCT,
                )
            ),
            min_neutral_win_rate=float(
                raw.get(
                    "min_neutral_win_rate",
                    FROZEN_MIN_NEUTRAL_WIN_RATE,
                )
            ),
            require_up_better_than_down=bool(
                raw.get(
                    "require_up_better_than_down",
                    FROZEN_REQUIRE_UP_BETTER_THAN_DOWN,
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
            "min_configured_average_pct": (
                FROZEN_MIN_CONFIGURED_AVERAGE_PCT
            ),
            "min_neutral_average_pct": (
                FROZEN_MIN_NEUTRAL_AVERAGE_PCT
            ),
            "min_neutral_median_pct": (
                FROZEN_MIN_NEUTRAL_MEDIAN_PCT
            ),
            "min_neutral_win_rate": (
                FROZEN_MIN_NEUTRAL_WIN_RATE
            ),
            "require_up_better_than_down": (
                FROZEN_REQUIRE_UP_BETTER_THAN_DOWN
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

    aud_cost = config.cost_of(
        FROZEN_TARGET
    )
    if not math.isclose(
        aud_cost,
        FROZEN_AUD_JPY_COST,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "AUD_JPY cost は0.005に固定しています。"
            f"実際: {aud_cost}"
        )

    aud_swap = config.swap_of(
        FROZEN_TARGET
    )
    if not math.isclose(
        aud_swap,
        FROZEN_AUD_JPY_SWAP,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "AUD_JPY swap は0.00891に固定しています。"
            f"実際: {aud_swap}"
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


def add_return_scenarios(
    trades: pd.DataFrame,
    config: FinalOosConfig,
) -> pd.DataFrame:
    result = trades.copy()

    entry_date = pd.to_datetime(
        result["entry_date"]
    )
    exit_date = pd.to_datetime(
        result["exit_date"]
    )

    holding_days = (
        exit_date - entry_date
    ).dt.days

    position_rate = result["position"].map(
        {
            "long": 1.0,
            "short": -1.0,
        }
    )

    if position_rate.isna().any():
        raise ValueError(
            "position にlong/short以外があります。"
        )

    swap_contribution_pct = (
        position_rate
        * FROZEN_AUD_JPY_SWAP
        * holding_days
    )

    result["holding_calendar_days"] = (
        holding_days
    )
    result["swap_contribution_pct"] = (
        swap_contribution_pct
    )

    # 既存backtestのprofit_pctから、固定swap寄与だけを逆算して除く。
    result["neutral_carry_profit_pct"] = (
        result["profit_pct"]
        - result["swap_contribution_pct"]
    )

    result["stress_profit_pct"] = (
        result["neutral_carry_profit_pct"]
        - config.stress_extra_cost_pct
    )

    result["passes_regime_filter"] = (
        result["regime_direction"]
        == config.filter_direction
    )

    return result


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
) -> pd.DataFrame:
    rows = []

    for regime in ("all", "up", "down"):
        if regime == "all":
            selected = trades
        else:
            selected = trades[
                trades["regime_direction"]
                == regime
            ]

        configured = summarize_values(
            selected["profit_pct"]
        )
        neutral = summarize_values(
            selected["neutral_carry_profit_pct"]
        )
        stress = summarize_values(
            selected["stress_profit_pct"]
        )

        row = {
            "regime_direction": regime,
        }

        for name, value in configured.items():
            row[f"configured_{name}"] = value

        for name, value in neutral.items():
            row[f"neutral_{name}"] = value

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
            f"summaryの {regime} 行を"
            "一意に取得できません。"
        )

    return rows.iloc[0]


def build_verdict(
    summary: pd.DataFrame,
    config: FinalOosConfig,
) -> pd.DataFrame:
    up = one_summary_row(
        summary,
        "up",
    )
    down = one_summary_row(
        summary,
        "down",
    )

    checks = {
        "enough_trades": (
            up["neutral_trade_count"]
            >= config.min_closed_trades
        ),
        "configured_average_positive": (
            up["configured_average_pct"]
            > config.min_configured_average_pct
        ),
        "neutral_average_positive": (
            up["neutral_average_pct"]
            > config.min_neutral_average_pct
        ),
        "neutral_median_positive": (
            up["neutral_median_pct"]
            > config.min_neutral_median_pct
        ),
        "neutral_win_rate_ok": (
            up["neutral_win_rate"]
            >= config.min_neutral_win_rate
        ),
        "stress_average_positive": (
            up["stress_average_pct"] > 0
        ),
        "up_better_than_down": (
            up["neutral_average_pct"]
            > down["neutral_average_pct"]
        ),
    }

    if not checks["enough_trades"]:
        verdict = "INCONCLUSIVE_TOO_FEW_TRADES"

    elif (
        not checks["configured_average_positive"]
        or not checks["neutral_average_positive"]
    ):
        verdict = "FAIL"

    elif (
        checks["neutral_median_positive"]
        and checks["neutral_win_rate_ok"]
        and checks["stress_average_positive"]
        and checks["up_better_than_down"]
    ):
        verdict = "STRONG_PASS"

    elif (
        checks["neutral_median_positive"]
        and checks["neutral_win_rate_ok"]
        and checks["stress_average_positive"]
        and not checks["up_better_than_down"]
    ):
        verdict = "STRATEGY_PASS_REGIME_FAIL"

    else:
        verdict = "WEAK_PASS"

    row = {
        "verdict": verdict,
        "period_start_year": config.period[0],
        "period_end_year": config.period[1],

        "up_trade_count": (
            up["neutral_trade_count"]
        ),

        "up_configured_average_pct": (
            up["configured_average_pct"]
        ),

        "up_neutral_average_pct": (
            up["neutral_average_pct"]
        ),
        "up_neutral_median_pct": (
            up["neutral_median_pct"]
        ),
        "up_neutral_win_rate": (
            up["neutral_win_rate"]
        ),
        "up_neutral_t_value": (
            up["neutral_t_value"]
        ),

        "up_stress_average_pct": (
            up["stress_average_pct"]
        ),

        "down_neutral_average_pct": (
            down["neutral_average_pct"]
        ),

        "up_minus_down_neutral_average_pct": (
            up["neutral_average_pct"]
            - down["neutral_average_pct"]
        ),

        "stress_extra_cost_pct": (
            config.stress_extra_cost_pct
        ),
    }

    row.update(checks)

    return pd.DataFrame([row])


def print_result(
    summary: pd.DataFrame,
    verdict: pd.DataFrame,
):
    columns = [
        "regime_direction",
        "configured_trade_count",
        "configured_average_pct",
        "neutral_average_pct",
        "neutral_median_pct",
        "neutral_win_rate",
        "neutral_t_value",
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
        "=== AUD_JPY <- EUR_GBP × AUD_JPY up "
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
        "sma / threshold=1 / counter=false / "
        "hold=20 / start=1 / SMA=15"
    )
    print(
        "Fixed regime: "
        "AUD_JPY前営業日終値 >= "
        "前営業日200日SMA"
    )
    print(
        "Configured AUD_JPY cost: 0.005"
    )
    print(
        "Configured AUD_JPY swap: "
        "+0.00891% / day for long"
    )
    print(
        "Stress: neutral-carry損益から "
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
            "AUD_JPY <- EUR_GBP の"
            "トレードがありません。"
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

    trades = add_return_scenarios(
        trades,
        final_config,
    )

    summary = build_summary(
        trades,
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
            "AUD_JPY <- EUR_GBP × AUD_JPY up "
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
