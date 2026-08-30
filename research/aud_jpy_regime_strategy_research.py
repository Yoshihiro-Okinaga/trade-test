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
    "aud_jpy_eur_gbp_regime_strategy_trades.csv"
)
SUMMARY_OUTPUT_FILE = (
    "aud_jpy_eur_gbp_regime_strategy_summary.csv"
)
COMPARISON_OUTPUT_FILE = (
    "aud_jpy_eur_gbp_regime_strategy_comparison.csv"
)
ROUND_DIGITS = 9

# ---------------------------------------------------------
# 2021+を見る前に固定した仮説。
# ---------------------------------------------------------
FROZEN_PERIODS = (
    (2001, 2005),
    (2006, 2010),
    (2011, 2015),
    (2016, 2020),
)
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

# 既存config.tomlのAUD_JPY取引条件も固定。
FROZEN_AUD_JPY_COST = 0.005
FROZEN_AUD_JPY_SWAP = 0.00891


@dataclass(frozen=True)
class AudJpyRegimeStrategyConfig:
    periods: tuple[tuple[int, int], ...]

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

    @classmethod
    def from_config_data(
        cls,
        config_data: dict,
    ):
        raw = config_data.get(
            "aud_jpy_regime_strategy_research",
            {},
        )

        periods = tuple(
            _parse_period(
                value,
                "aud_jpy_regime_strategy_research.periods",
            )
            for value in raw.get(
                "periods",
                FROZEN_PERIODS,
            )
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
                "aud_jpy_regime_strategy_research."
                "signal_type が不正です。"
            ) from exc

        config = cls(
            periods=periods,
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
        )

        config.validate_frozen_hypothesis()
        return config

    def validate_frozen_hypothesis(self):
        expected = {
            "periods": FROZEN_PERIODS,
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
        }

        for name, expected_value in expected.items():
            actual = getattr(self, name)
            if actual != expected_value:
                raise ValueError(
                    f"{name} は2021+を見る前に "
                    f"{expected_value!r} "
                    f"へ固定しています。"
                    f"実際: {actual!r}"
                )

    @property
    def final_development_year(self) -> int:
        return max(
            end_year
            for _start_year, end_year
            in self.periods
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
    """代表戦略選抜時の本体条件が変わっていないか確認する。"""
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
            "extra_cost_pct は0に固定してください。"
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

    cost = config.cost_of(FROZEN_TARGET)
    if not math.isclose(
        cost,
        FROZEN_AUD_JPY_COST,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "AUD_JPY cost は0.005に固定しています。"
            f"実際: {cost}"
        )

    swap = config.swap_of(FROZEN_TARGET)
    if not math.isclose(
        swap,
        FROZEN_AUD_JPY_SWAP,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "AUD_JPY swap は0.00891に固定しています。"
            f"実際: {swap}"
        )


def trim_market_data_end_year(
    market_data: MarketData,
    end_year: int,
):
    """2021+を研究計算へ入れないため、2020年末で切る。"""
    market_data.df = market_data.df[
        market_data.df["日付"].dt.year <= end_year
    ].copy()


def build_task_caches(
    task: StrategyTask,
    end_year: int,
    data_folder=None,
):
    """この1戦略に必要なキャッシュだけを作る。"""
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
    """entry日の前営業日までのTarget価格だけでup/downを作る。"""
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


def add_fixed_strategy_columns(
    trades: pd.DataFrame,
    config: AudJpyRegimeStrategyConfig,
) -> pd.DataFrame:
    result = trades.copy()

    columns = [
        ("target", config.target),
        ("ref", config.ref),
        ("signal_type", config.signal_type),
        (
            "counter_trade",
            config.counter_trade,
        ),
        (
            "use_excess_return",
            config.use_excess_return,
        ),
        (
            "threshold_width",
            config.threshold_width,
        ),
        ("hold_days", config.hold_days),
        ("start_days", config.start_days),
        ("sma_period", config.sma_period),
        (
            "direction_sma_window",
            config.direction_sma_window,
        ),
        (
            "filter_direction",
            config.filter_direction,
        ),
    ]

    for index, (name, value) in enumerate(columns):
        result.insert(index, name, value)

    result["passes_regime_filter"] = (
        result["regime_direction"]
        == config.filter_direction
    )

    return result


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
    config: AudJpyRegimeStrategyConfig,
) -> pd.DataFrame:
    rows = []

    for period in config.periods:
        period_trades = restrict_period(
            trades,
            period,
        )

        for regime in (
            "all",
            "up",
            "down",
        ):
            if regime == "all":
                regime_trades = period_trades
            else:
                regime_trades = period_trades[
                    period_trades["regime_direction"]
                    == regime
                ]

            for position in (
                "all",
                "long",
                "short",
            ):
                if position == "all":
                    selected = regime_trades
                else:
                    selected = regime_trades[
                        regime_trades["position"]
                        == position
                    ]

                row = {
                    "period_start_year": period[0],
                    "period_end_year": period[1],
                    "regime_direction": regime,
                    "position": position,
                }
                row.update(
                    summarize_values(
                        selected["profit_pct"]
                    )
                )
                rows.append(row)

    return pd.DataFrame(rows)


def _summary_row(
    summary: pd.DataFrame,
    start_year: int,
    end_year: int,
    regime: str,
) -> pd.Series:
    rows = summary[
        (
            summary["period_start_year"]
            == start_year
        )
        & (
            summary["period_end_year"]
            == end_year
        )
        & (
            summary["regime_direction"]
            == regime
        )
        & (
            summary["position"]
            == "all"
        )
    ]

    if len(rows) != 1:
        raise ValueError(
            "summary行を一意に取得できません: "
            f"{start_year}-{end_year}, {regime}"
        )

    return rows.iloc[0]


def build_comparison(
    summary: pd.DataFrame,
    config: AudJpyRegimeStrategyConfig,
) -> pd.DataFrame:
    rows = []

    for start_year, end_year in config.periods:
        all_row = _summary_row(
            summary,
            start_year,
            end_year,
            "all",
        )
        up_row = _summary_row(
            summary,
            start_year,
            end_year,
            "up",
        )
        down_row = _summary_row(
            summary,
            start_year,
            end_year,
            "down",
        )

        rows.append({
            "period_start_year": start_year,
            "period_end_year": end_year,
            "all_trade_count": (
                all_row["trade_count"]
            ),
            "all_average_pct": (
                all_row["average_pct"]
            ),
            "all_median_pct": (
                all_row["median_pct"]
            ),
            "all_win_rate": (
                all_row["win_rate"]
            ),
            "up_trade_count": (
                up_row["trade_count"]
            ),
            "up_average_pct": (
                up_row["average_pct"]
            ),
            "up_median_pct": (
                up_row["median_pct"]
            ),
            "up_win_rate": (
                up_row["win_rate"]
            ),
            "up_t_value": (
                up_row["t_value"]
            ),
            "down_trade_count": (
                down_row["trade_count"]
            ),
            "down_average_pct": (
                down_row["average_pct"]
            ),
            "down_median_pct": (
                down_row["median_pct"]
            ),
            "down_win_rate": (
                down_row["win_rate"]
            ),
            "up_minus_down_average_pct": (
                up_row["average_pct"]
                - down_row["average_pct"]
            ),
            "up_minus_all_average_pct": (
                up_row["average_pct"]
                - all_row["average_pct"]
            ),
        })

    return pd.DataFrame(rows)


def print_comparison(
    comparison: pd.DataFrame,
):
    print(
        "\n=== AUD_JPY <- EUR_GBP × AUD_JPY direction ==="
    )

    columns = [
        "period_start_year",
        "period_end_year",
        "all_trade_count",
        "all_average_pct",
        "up_trade_count",
        "up_average_pct",
        "down_trade_count",
        "down_average_pct",
        "up_minus_down_average_pct",
    ]

    print(
        comparison[columns].to_string(
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
        AudJpyRegimeStrategyConfig.from_config_data(
            config_data
        )
    )

    validate_backtest_environment(
        backtest_config
    )

    task = research_config.to_task()

    print(
        "=== AUD_JPY <- EUR_GBP Regime Strategy "
        "Development Check ==="
    )
    print(
        "2021年以降は今回の計算対象に入れません。"
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
        "Existing AUD_JPY cost: "
        f"{backtest_config.cost_of(FROZEN_TARGET)}"
    )
    print(
        "Existing AUD_JPY swap: "
        f"{backtest_config.swap_of(FROZEN_TARGET)}% / day"
    )

    (
        ref_cache,
        target_cache,
        target_prices,
    ) = build_task_caches(
        task,
        research_config.final_development_year,
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
        research_config.direction_sma_window,
    )
    trades = attach_direction(
        trades,
        direction_frame,
    )
    trades = add_fixed_strategy_columns(
        trades,
        research_config,
    )

    # 出力も2001-2020だけに限定。
    trades = trades[
        trades["entry_year"]
        <= research_config.final_development_year
    ].copy()

    summary = build_summary(
        trades,
        research_config,
    )
    comparison = build_comparison(
        summary,
        research_config,
    )

    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    trade_path = save_dir / TRADE_OUTPUT_FILE
    summary_path = save_dir / SUMMARY_OUTPUT_FILE
    comparison_path = (
        save_dir / COMPARISON_OUTPUT_FILE
    )

    trades.to_csv(
        trade_path,
        **csv_options,
    )
    summary.to_csv(
        summary_path,
        **csv_options,
    )
    comparison.to_csv(
        comparison_path,
        **csv_options,
    )

    print_comparison(
        comparison
    )

    print("\n出力:")
    print(f"  {trade_path}")
    print(f"  {summary_path}")
    print(f"  {comparison_path}")
    print(
        "\nこのStepではルールを変更しません。"
        "既存Regime研究を実トレード単位で"
        "再確認するだけです。"
    )

    return (
        trade_path,
        summary_path,
        comparison_path,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "AUD_JPY <- EUR_GBP × AUD_JPY up "
            "固定仮説を2001-2020で再確認する。"
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
