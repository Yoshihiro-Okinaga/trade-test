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

from market_data import MarketData
from pair_statistics import (
    align_prices,
    calculate_rolling_z_score,
    calculate_spread,
    calculate_spread_with_coefficients,
)


ROUND_DIGITS = 9

# development結果を上書きしないよう、最終OOSは専用名にする。
TRADE_OUTPUT_FILE = "pair_strategy_final_oos_trades.csv"
SUMMARY_OUTPUT_FILE = "pair_strategy_final_oos_summary.csv"
PORTFOLIO_OUTPUT_FILE = "pair_strategy_final_oos_portfolio.csv"
PORTFOLIO_SUMMARY_OUTPUT_FILE = (
    "pair_strategy_final_oos_portfolio_summary.csv"
)

# 2021+を見る前に凍結した最終OOS条件。
# config.toml がこの値から1つでも変わっていたら実行を止める。
# 2026年はあえて読まず、2021-2025の5年間だけを最終OOSにする。
FROZEN_EVALUATION_PERIOD = (2021, 2025)
FROZEN_HEDGE_FIT_PERIOD = (2001, 2015)
FROZEN_PAIRS = (
    ("9502_中部電力", "9503_関西電力"),
    ("9502_中部電力", "9508_九州電力"),
)
FROZEN_Z_LOOKBACK = 60
FROZEN_ENTRY_Z = 2.0
FROZEN_MAX_HOLD_DAYS = 20
FROZEN_ENTRY_DELAY_DAYS = 1
FROZEN_PRIMARY_COST_SCENARIO = "baseline"
FROZEN_PORTFOLIO_MODE = "fixed_pair_sleeves"
FROZEN_PAIR_ALLOCATIONS = (
    ("9502_中部電力", "9503_関西電力", 0.5),
    ("9502_中部電力", "9508_九州電力", 0.5),
)
FROZEN_RETURN_BASIS = (
    "split_adjusted_close_price_only_no_dividends"
)


@dataclass(frozen=True)
class CostScenario:
    name: str
    transaction_cost_bps_per_turnover: float
    short_borrow_bps_per_day: float


@dataclass(frozen=True)
class PairStrategyConfig:
    evaluation_period: tuple[int, int]
    hedge_fit_period: tuple[int, int]
    pairs: tuple[tuple[str, str], ...]

    z_lookback: int
    entry_z: float
    max_hold_days: int
    entry_delay_days: int

    cost_scenarios: tuple[CostScenario, ...]
    primary_cost_scenario: str

    portfolio_mode: str
    pair_allocations: tuple[tuple[str, str, float], ...]
    return_basis: str

    @classmethod
    def from_config_data(cls, config_data: dict):
        section = config_data.get(
            "pair_strategy_research",
            {},
        )

        evaluation_period = _parse_period(
            section.get("period", [2016, 2020]),
            "pair_strategy_research.period",
        )
        hedge_fit_period = _parse_period(
            section.get(
                "hedge_fit_period",
                [2001, 2015],
            ),
            "pair_strategy_research.hedge_fit_period",
        )

        if hedge_fit_period[1] >= evaluation_period[0]:
            raise ValueError(
                "hedge_fit_period は評価期間より前にしてください。"
            )

        pairs = _parse_pairs(
            section.get(
                "pairs",
                [
                    ["9502_中部電力", "9503_関西電力"],
                    ["9502_中部電力", "9508_九州電力"],
                ],
            )
        )

        config = cls(
            evaluation_period=evaluation_period,
            hedge_fit_period=hedge_fit_period,
            pairs=pairs,
            z_lookback=int(
                section.get("z_lookback", 60)
            ),
            entry_z=float(
                section.get("entry_z", 2.0)
            ),
            max_hold_days=int(
                section.get("max_hold_days", 20)
            ),
            entry_delay_days=int(
                section.get("entry_delay_days", 1)
            ),
            cost_scenarios=_parse_cost_scenarios(
                section.get(
                    "cost_scenarios",
                    [
                        {
                            "name": "baseline",
                            "transaction_cost_bps_per_turnover": 10.0,
                            "short_borrow_bps_per_day": 0.5,
                        },
                        {
                            "name": "stress",
                            "transaction_cost_bps_per_turnover": 20.0,
                            "short_borrow_bps_per_day": 1.0,
                        },
                    ],
                )
            ),
            primary_cost_scenario=str(
                section.get(
                    "primary_cost_scenario",
                    "baseline",
                )
            ),
            portfolio_mode=str(
                section.get(
                    "portfolio_mode",
                    "fixed_pair_sleeves",
                )
            ),
            pair_allocations=_parse_pair_allocations(
                section.get(
                    "pair_allocations",
                    [
                        {
                            "symbol_a": "9502_中部電力",
                            "symbol_b": "9503_関西電力",
                            "capital_fraction": 0.5,
                        },
                        {
                            "symbol_a": "9502_中部電力",
                            "symbol_b": "9508_九州電力",
                            "capital_fraction": 0.5,
                        },
                    ],
                )
            ),
            return_basis=str(
                section.get(
                    "return_basis",
                    FROZEN_RETURN_BASIS,
                )
            ),
        )
        config.validate()
        return config

    def validate(self):
        if self.z_lookback < 20:
            raise ValueError(
                "z_lookback は20以上にしてください。"
            )
        if self.entry_z <= 0:
            raise ValueError(
                "entry_z は0より大きくしてください。"
            )
        if self.max_hold_days < 1:
            raise ValueError(
                "max_hold_days は1以上にしてください。"
            )
        if self.entry_delay_days < 1:
            raise ValueError(
                "entry_delay_days は1以上にしてください。"
            )
        scenario_names = {
            scenario.name
            for scenario in self.cost_scenarios
        }
        if self.primary_cost_scenario not in scenario_names:
            raise ValueError(
                "primary_cost_scenario が "
                "cost_scenarios にありません。"
            )

        if self.portfolio_mode != "fixed_pair_sleeves":
            raise ValueError(
                "portfolio_mode は fixed_pair_sleeves に固定します。"
            )

        pair_keys = {
            (symbol_a, symbol_b)
            for symbol_a, symbol_b in self.pairs
        }
        allocation_keys = {
            (symbol_a, symbol_b)
            for symbol_a, symbol_b, _fraction
            in self.pair_allocations
        }
        if pair_keys != allocation_keys:
            raise ValueError(
                "pair_allocations は pairs と同じペアを"
                "1組ずつ指定してください。"
            )

        total_fraction = sum(
            fraction
            for _symbol_a, _symbol_b, fraction
            in self.pair_allocations
        )
        if total_fraction > 1.0 + 1e-12:
            raise ValueError(
                "pair_allocations の capital_fraction 合計は"
                "1.0以下にしてください。"
            )

        self.validate_final_oos_freeze()

    def validate_final_oos_freeze(self):
        """2021+を見る前に決めた条件から変更されていないか確認する。"""
        if self.evaluation_period != FROZEN_EVALUATION_PERIOD:
            raise ValueError(
                "最終OOSの period は "
                f"{list(FROZEN_EVALUATION_PERIOD)} に固定しています。"
            )

        if self.hedge_fit_period != FROZEN_HEDGE_FIT_PERIOD:
            raise ValueError(
                "最終OOSの hedge_fit_period は "
                f"{list(FROZEN_HEDGE_FIT_PERIOD)} に固定しています。"
            )

        if self.pairs != FROZEN_PAIRS:
            raise ValueError(
                "最終OOSの pairs が凍結条件と一致しません。"
            )

        frozen_scalars = [
            ("z_lookback", self.z_lookback, FROZEN_Z_LOOKBACK),
            ("entry_z", self.entry_z, FROZEN_ENTRY_Z),
            (
                "max_hold_days",
                self.max_hold_days,
                FROZEN_MAX_HOLD_DAYS,
            ),
            (
                "entry_delay_days",
                self.entry_delay_days,
                FROZEN_ENTRY_DELAY_DAYS,
            ),
            (
                "primary_cost_scenario",
                self.primary_cost_scenario,
                FROZEN_PRIMARY_COST_SCENARIO,
            ),
            (
                "portfolio_mode",
                self.portfolio_mode,
                FROZEN_PORTFOLIO_MODE,
            ),
            (
                "return_basis",
                self.return_basis,
                FROZEN_RETURN_BASIS,
            ),
        ]
        for name, actual, expected in frozen_scalars:
            if actual != expected:
                raise ValueError(
                    f"最終OOSの {name} は {expected!r} "
                    f"に固定しています。実際: {actual!r}"
                )

        if self.pair_allocations != FROZEN_PAIR_ALLOCATIONS:
            raise ValueError(
                "最終OOSの pair_allocations は50/50に固定しています。"
            )

        expected_costs = {
            "baseline": (10.0, 0.5),
            "stress": (20.0, 1.0),
        }
        actual_costs = {
            scenario.name: (
                scenario.transaction_cost_bps_per_turnover,
                scenario.short_borrow_bps_per_day,
            )
            for scenario in self.cost_scenarios
        }
        if actual_costs != expected_costs:
            raise ValueError(
                "最終OOSのcost_scenariosが凍結条件と一致しません。"
            )


def _parse_pair_allocations(
    values,
) -> tuple[tuple[str, str, float], ...]:
    allocations = []
    seen = set()

    for value in values:
        symbol_a = str(value["symbol_a"])
        symbol_b = str(value["symbol_b"])
        fraction = float(value["capital_fraction"])

        key = (symbol_a, symbol_b)
        if key in seen:
            raise ValueError(
                f"pair_allocations が重複しています: "
                f"{symbol_a} / {symbol_b}"
            )
        if not 0.0 < fraction <= 1.0:
            raise ValueError(
                "capital_fraction は0より大きく"
                "1以下にしてください。"
            )

        seen.add(key)
        allocations.append(
            (symbol_a, symbol_b, fraction)
        )

    if not allocations:
        raise ValueError(
            "pair_allocations を1組以上指定してください。"
        )

    return tuple(allocations)


def _parse_cost_scenarios(
    values,
) -> tuple[CostScenario, ...]:
    scenarios = []
    names = set()

    for value in values:
        name = str(value["name"]).strip()
        if not name:
            raise ValueError(
                "cost_scenarios.name は空にできません。"
            )
        if name in names:
            raise ValueError(
                f"cost scenario名が重複しています: {name}"
            )

        transaction_cost = float(
            value.get(
                "transaction_cost_bps_per_turnover",
                0.0,
            )
        )
        short_borrow = float(
            value.get(
                "short_borrow_bps_per_day",
                0.0,
            )
        )
        if transaction_cost < 0 or short_borrow < 0:
            raise ValueError(
                "cost_scenarios のコストは0以上にしてください。"
            )

        names.add(name)
        scenarios.append(
            CostScenario(
                name=name,
                transaction_cost_bps_per_turnover=(
                    transaction_cost
                ),
                short_borrow_bps_per_day=short_borrow,
            )
        )

    if not scenarios:
        raise ValueError(
            "cost_scenarios を1つ以上指定してください。"
        )

    return tuple(scenarios)


def _parse_period(
    value,
    field_name: str,
) -> tuple[int, int]:
    if len(value) != 2:
        raise ValueError(
            f"{field_name} は [開始年, 終了年] "
            "の2要素で指定してください。"
        )

    start_year = int(value[0])
    end_year = int(value[1])
    if start_year > end_year:
        raise ValueError(
            f"{field_name} は 開始年 <= 終了年 "
            "にしてください。"
        )

    return start_year, end_year


def _parse_pairs(
    values,
) -> tuple[tuple[str, str], ...]:
    pairs = []
    seen = set()

    for value in values:
        if len(value) != 2:
            raise ValueError(
                "pair_strategy_research.pairs の各要素は"
                " [銘柄A, 銘柄B] にしてください。"
            )

        symbol_a = str(value[0])
        symbol_b = str(value[1])
        if symbol_a == symbol_b:
            raise ValueError(
                f"同一銘柄のペアは使えません: {symbol_a}"
            )

        key = frozenset((symbol_a, symbol_b))
        if key in seen:
            raise ValueError(
                f"重複ペアがあります: "
                f"{symbol_a} / {symbol_b}"
            )

        seen.add(key)
        pairs.append((symbol_a, symbol_b))

    if not pairs:
        raise ValueError(
            "pair_strategy_research.pairs を"
            "1組以上指定してください。"
        )

    return tuple(pairs)


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


def load_close_data(
    symbol_name: str,
    data_folder=None,
) -> pd.DataFrame:
    return MarketData(
        symbol_name,
        data_folder,
    ).df[["日付", "終値"]].copy()


def build_pair_frame(
    symbol_a: str,
    symbol_b: str,
    config: PairStrategyConfig,
    data_folder=None,
) -> tuple[pd.DataFrame, float, float]:
    data_a = load_close_data(
        symbol_a,
        data_folder,
    )
    data_b = load_close_data(
        symbol_b,
        data_folder,
    )

    fit_start, fit_end = config.hedge_fit_period
    eval_start, eval_end = config.evaluation_period

    fit_aligned = align_prices(
        data_a,
        data_b,
        start_year=fit_start,
        end_year=fit_end,
    )
    if len(fit_aligned) < config.z_lookback:
        raise ValueError(
            f"{symbol_a} / {symbol_b}: "
            "hedge推定期間のデータが不足しています。"
        )

    fit_log_a = np.log(
        fit_aligned["price_a"].to_numpy(dtype=float)
    )
    fit_log_b = np.log(
        fit_aligned["price_b"].to_numpy(dtype=float)
    )
    alpha, beta, _ = calculate_spread(
        fit_log_a,
        fit_log_b,
    )

    if not math.isfinite(beta) or beta <= 0:
        raise ValueError(
            f"{symbol_a} / {symbol_b}: "
            f"hedge ratio が正ではありません: {beta}"
        )

    # z-scoreの先頭を評価期間の境界でリセットしない。
    # 実運用では2016年初にも2015年末までの情報を利用できるため、
    # hedge推定開始年から評価終了年まで連続したspreadを作る。
    full_aligned = align_prices(
        data_a,
        data_b,
        start_year=fit_start,
        end_year=eval_end,
    )

    log_a = np.log(
        full_aligned["price_a"].to_numpy(dtype=float)
    )
    log_b = np.log(
        full_aligned["price_b"].to_numpy(dtype=float)
    )
    spread = calculate_spread_with_coefficients(
        log_a,
        log_b,
        alpha,
        beta,
    )
    z_score = calculate_rolling_z_score(
        spread,
        config.z_lookback,
    )

    frame = full_aligned.copy()
    frame["spread"] = spread
    frame["z_score"] = z_score
    frame["in_evaluation"] = (
        (frame["日付"].dt.year >= eval_start)
        & (frame["日付"].dt.year <= eval_end)
    )

    return frame, alpha, beta


def find_excursion_signals(
    frame: pd.DataFrame,
    entry_z: float,
) -> list[tuple[int, int]]:
    """2σ超えを1イベント1回だけシグナル化する。

    direction:
        +1: spreadが上側へ乖離
        -1: spreadが下側へ乖離

    z=0を跨ぐまで同じ乖離イベントとして扱う。
    """
    signals = []
    in_excursion = False
    direction = 0

    for index, row in frame.iterrows():
        z_value = row["z_score"]
        if not math.isfinite(float(z_value)):
            continue

        if not in_excursion:
            if z_value >= entry_z:
                if bool(row["in_evaluation"]):
                    signals.append((index, 1))
                in_excursion = True
                direction = 1
            elif z_value <= -entry_z:
                if bool(row["in_evaluation"]):
                    signals.append((index, -1))
                in_excursion = True
                direction = -1
            continue

        if direction > 0 and z_value <= 0:
            in_excursion = False
            direction = 0
        elif direction < 0 and z_value >= 0:
            in_excursion = False
            direction = 0

    return signals


def find_exit_index(
    frame: pd.DataFrame,
    entry_index: int,
    signal_direction: int,
    max_hold_days: int,
) -> tuple[int | None, str]:
    """zero crossを確認した翌営業日、または20日で終了する。"""
    last_index = len(frame) - 1
    max_exit_index = entry_index + max_hold_days

    # 最大保有日は事前に分かるため、その日の終値で終了できる。
    forced_exit_index = (
        max_exit_index
        if max_exit_index <= last_index
        else None
    )

    # zero crossは当日終値で初めて確定するため、
    # 実際の決済はその翌営業日終値とする。
    zero_cross_exit_index = None
    search_end = (
        forced_exit_index
        if forced_exit_index is not None
        else last_index
    )

    for index in range(entry_index, search_end + 1):
        z_value = float(frame.at[index, "z_score"])
        if not math.isfinite(z_value):
            continue

        crossed = (
            signal_direction > 0
            and z_value <= 0
        ) or (
            signal_direction < 0
            and z_value >= 0
        )
        if not crossed:
            continue

        candidate = index + 1
        if candidate <= last_index:
            zero_cross_exit_index = candidate
        break

    candidates = []
    if forced_exit_index is not None:
        candidates.append(
            (forced_exit_index, "max_hold")
        )
    if zero_cross_exit_index is not None:
        candidates.append(
            (zero_cross_exit_index, "zero_cross")
        )

    if not candidates:
        return None, "period_end"

    return min(
        candidates,
        key=lambda item: item[0],
    )


def normalized_weights(
    beta: float,
    signal_direction: int,
) -> tuple[float, float]:
    """OLS betaを使い、絶対ウェイト合計を1に正規化する。

    spread = log(A) - alpha - beta*log(B)

    spread上側乖離:
        Aを売り、Bを買う
    spread下側乖離:
        Aを買い、Bを売る
    """
    denominator = 1.0 + abs(beta)
    a_abs = 1.0 / denominator
    b_abs = abs(beta) / denominator

    if signal_direction > 0:
        return -a_abs, b_abs
    return a_abs, -b_abs


def calculate_trade_return(
    entry_a: float,
    exit_a: float,
    entry_b: float,
    exit_b: float,
    weight_a: float,
    weight_b: float,
    holding_days: int,
    scenario: CostScenario,
) -> tuple[float, float, float, float]:
    return_a = exit_a / entry_a - 1.0
    return_b = exit_b / entry_b - 1.0

    gross_return = (
        weight_a * return_a
        + weight_b * return_b
    )

    # gross notional=1。entryとexitで計2回turnoverする。
    transaction_cost = (
        2.0
        * scenario.transaction_cost_bps_per_turnover
        / 10000.0
    )

    short_weight = (
        abs(weight_a)
        if weight_a < 0
        else abs(weight_b)
    )
    short_borrow_cost = (
        short_weight
        * holding_days
        * scenario.short_borrow_bps_per_day
        / 10000.0
    )

    net_return = (
        gross_return
        - transaction_cost
        - short_borrow_cost
    )

    return (
        gross_return * 100.0,
        transaction_cost * 100.0,
        short_borrow_cost * 100.0,
        net_return * 100.0,
    )


def build_trades_for_pair(
    symbol_a: str,
    symbol_b: str,
    frame: pd.DataFrame,
    alpha: float,
    beta: float,
    config: PairStrategyConfig,
) -> list[dict]:
    eval_start, eval_end = config.evaluation_period
    signals = find_excursion_signals(
        frame,
        config.entry_z,
    )
    trades = []

    for signal_index, direction in signals:
        entry_index = (
            signal_index
            + config.entry_delay_days
        )
        if entry_index >= len(frame):
            continue

        entry_date = frame.at[entry_index, "日付"]
        if not (
            eval_start
            <= entry_date.year
            <= eval_end
        ):
            continue

        exit_index, exit_reason = find_exit_index(
            frame,
            entry_index,
            direction,
            config.max_hold_days,
        )

        weight_a, weight_b = normalized_weights(
            beta,
            direction,
        )

        base_row = {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "hedge_alpha": alpha,
            "hedge_ratio": beta,
            "z_lookback": config.z_lookback,
            "entry_z": config.entry_z,
            "entry_delay_days": (
                config.entry_delay_days
            ),
            "max_hold_days": config.max_hold_days,
            "signal_direction": direction,
            "signal_date": frame.at[
                signal_index,
                "日付",
            ],
            "signal_z": frame.at[
                signal_index,
                "z_score",
            ],
            "entry_date": entry_date,
            "entry_z_actual": frame.at[
                entry_index,
                "z_score",
            ],
            "weight_a": weight_a,
            "weight_b": weight_b,
            "entry_price_a": frame.at[
                entry_index,
                "price_a",
            ],
            "entry_price_b": frame.at[
                entry_index,
                "price_b",
            ],
            "exit_reason": exit_reason,
        }

        if exit_index is None:
            base_row.update({
                "status": "open_at_period_end",
                "exit_date": pd.NaT,
                "holding_days": np.nan,
                "exit_price_a": np.nan,
                "exit_price_b": np.nan,
                "gross_return_pct": np.nan,
            })
            trades.append(base_row)
            continue

        exit_date = frame.at[exit_index, "日付"]
        if exit_date.year > eval_end:
            base_row.update({
                "status": "open_at_period_end",
                "exit_date": pd.NaT,
                "holding_days": np.nan,
                "exit_price_a": np.nan,
                "exit_price_b": np.nan,
                "gross_return_pct": np.nan,
            })
            trades.append(base_row)
            continue

        holding_days = exit_index - entry_index
        exit_a = float(
            frame.at[exit_index, "price_a"]
        )
        exit_b = float(
            frame.at[exit_index, "price_b"]
        )

        # grossはcost 0のシナリオで計算する。
        gross_scenario = CostScenario(
            name="gross",
            transaction_cost_bps_per_turnover=0.0,
            short_borrow_bps_per_day=0.0,
        )
        (
            gross_return_pct,
            _transaction_cost_pct,
            _short_borrow_cost_pct,
            _net_return_pct,
        ) = calculate_trade_return(
            float(
                frame.at[entry_index, "price_a"]
            ),
            exit_a,
            float(
                frame.at[entry_index, "price_b"]
            ),
            exit_b,
            weight_a,
            weight_b,
            holding_days,
            gross_scenario,
        )

        base_row.update({
            "status": "closed",
            "exit_date": exit_date,
            "holding_days": holding_days,
            "exit_price_a": exit_a,
            "exit_price_b": exit_b,
            "gross_return_pct": gross_return_pct,
        })

        for scenario in config.cost_scenarios:
            (
                _gross_return_pct,
                transaction_cost_pct,
                short_borrow_cost_pct,
                net_return_pct,
            ) = calculate_trade_return(
                float(
                    frame.at[entry_index, "price_a"]
                ),
                exit_a,
                float(
                    frame.at[entry_index, "price_b"]
                ),
                exit_b,
                weight_a,
                weight_b,
                holding_days,
                scenario,
            )
            prefix = scenario.name
            base_row[
                f"{prefix}_transaction_cost_pct"
            ] = transaction_cost_pct
            base_row[
                f"{prefix}_short_borrow_cost_pct"
            ] = short_borrow_cost_pct
            base_row[
                f"{prefix}_net_return_pct"
            ] = net_return_pct
        trades.append(base_row)

    return trades


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
    trade_frame: pd.DataFrame,
    config: PairStrategyConfig,
) -> pd.DataFrame:
    rows = []

    for symbol_a, symbol_b in config.pairs:
        pair_trades = trade_frame[
            (trade_frame["symbol_a"] == symbol_a)
            & (trade_frame["symbol_b"] == symbol_b)
            & (trade_frame["status"] == "closed")
        ]

        row = {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "evaluation_start_year": (
                config.evaluation_period[0]
            ),
            "evaluation_end_year": (
                config.evaluation_period[1]
            ),
            "hedge_fit_start_year": (
                config.hedge_fit_period[0]
            ),
            "hedge_fit_end_year": (
                config.hedge_fit_period[1]
            ),
            "z_lookback": config.z_lookback,
            "entry_z": config.entry_z,
            "entry_delay_days": (
                config.entry_delay_days
            ),
            "max_hold_days": (
                config.max_hold_days
            ),
            "open_at_period_end": int(
                (
                    (
                        trade_frame["symbol_a"]
                        == symbol_a
                    )
                    & (
                        trade_frame["symbol_b"]
                        == symbol_b
                    )
                    & (
                        trade_frame["status"]
                        == "open_at_period_end"
                    )
                ).sum()
            ),
        }

        gross = summarize_values(
            pair_trades["gross_return_pct"]
        )
        for name, value in gross.items():
            row[f"gross_{name}"] = value

        for scenario in config.cost_scenarios:
            row[
                f"{scenario.name}_transaction_cost_bps_per_turnover"
            ] = scenario.transaction_cost_bps_per_turnover
            row[
                f"{scenario.name}_short_borrow_bps_per_day"
            ] = scenario.short_borrow_bps_per_day

            stats = summarize_values(
                pair_trades[
                    f"{scenario.name}_net_return_pct"
                ]
            )
            for name, value in stats.items():
                row[
                    f"{scenario.name}_{name}"
                ] = value

        rows.append(row)

    return pd.DataFrame(rows)


def allocation_map(
    config: PairStrategyConfig,
) -> dict[tuple[str, str], float]:
    return {
        (symbol_a, symbol_b): fraction
        for symbol_a, symbol_b, fraction
        in config.pair_allocations
    }


def build_portfolio(
    trade_frame: pd.DataFrame,
    config: PairStrategyConfig,
) -> pd.DataFrame:
    """各Pairへ事前固定した資金枠を割り当てる。

    中部/関西 50%、中部/九州 50% のようにPairごとに
    専用sleeveを持つ。異なるPairのsignalは同時に採用できる。
    片方だけ建っている間は、もう片方の資金枠は現金のまま。

    過去成績による優先順位は使わない。
    """
    allocations = allocation_map(config)
    portfolio = trade_frame.copy()

    portfolio["capital_fraction"] = [
        allocations[(symbol_a, symbol_b)]
        for symbol_a, symbol_b in zip(
            portfolio["symbol_a"],
            portfolio["symbol_b"],
        )
    ]

    portfolio["portfolio_status"] = "accepted"
    portfolio["portfolio_reason"] = ""

    portfolio[
        "gross_portfolio_contribution_pct"
    ] = (
        portfolio["capital_fraction"]
        * portfolio["gross_return_pct"]
    )

    for scenario in config.cost_scenarios:
        portfolio[
            f"{scenario.name}_portfolio_contribution_pct"
        ] = (
            portfolio["capital_fraction"]
            * portfolio[
                f"{scenario.name}_net_return_pct"
            ]
        )

    return portfolio.sort_values(
        ["signal_date", "symbol_a", "symbol_b"]
    ).reset_index(drop=True)


def compounded_growth(
    returns_pct: pd.Series,
) -> float:
    values = pd.to_numeric(
        returns_pct,
        errors="coerce",
    ).dropna()

    growth = 1.0
    for value in values:
        growth *= 1.0 + float(value) / 100.0
    return growth


def portfolio_terminal_return_pct(
    portfolio_frame: pd.DataFrame,
    config: PairStrategyConfig,
    return_column: str,
) -> float:
    allocations = allocation_map(config)
    total_fraction = sum(allocations.values())
    ending_equity = 1.0 - total_fraction

    for (
        symbol_a,
        symbol_b,
    ), fraction in allocations.items():
        pair_trades = portfolio_frame[
            (portfolio_frame["symbol_a"] == symbol_a)
            & (portfolio_frame["symbol_b"] == symbol_b)
            & (portfolio_frame["status"] == "closed")
        ].sort_values("entry_date")

        sleeve_growth = compounded_growth(
            pair_trades[return_column]
        )
        ending_equity += (
            fraction * sleeve_growth
        )

    return (ending_equity - 1.0) * 100.0


def cagr_pct(
    terminal_return_pct: float,
    years: int,
) -> float:
    if years <= 0:
        return float("nan")

    ending_equity = (
        1.0 + terminal_return_pct / 100.0
    )
    if ending_equity <= 0:
        return float("nan")

    return (
        ending_equity ** (1.0 / years) - 1.0
    ) * 100.0


def build_portfolio_summary(
    portfolio_frame: pd.DataFrame,
    config: PairStrategyConfig,
) -> pd.DataFrame:
    rows = []
    allocations = allocation_map(config)
    years = (
        config.evaluation_period[1]
        - config.evaluation_period[0]
        + 1
    )

    overall = {
        "scope": "portfolio_all",
        "portfolio_mode": config.portfolio_mode,
        "trade_count": int(
            (
                portfolio_frame["status"]
                == "closed"
            ).sum()
        ),
        "total_capital_fraction": sum(
            allocations.values()
        ),
        "primary_cost_scenario": (
            config.primary_cost_scenario
        ),
    }

    gross_stats = summarize_values(
        portfolio_frame[
            "gross_portfolio_contribution_pct"
        ]
    )
    for name, value in gross_stats.items():
        overall[f"gross_{name}"] = value

    gross_terminal = portfolio_terminal_return_pct(
        portfolio_frame,
        config,
        "gross_return_pct",
    )
    overall[
        "gross_terminal_return_pct"
    ] = gross_terminal
    overall["gross_cagr_pct"] = cagr_pct(
        gross_terminal,
        years,
    )

    for scenario in config.cost_scenarios:
        overall[
            f"{scenario.name}_transaction_cost_bps_per_turnover"
        ] = scenario.transaction_cost_bps_per_turnover
        overall[
            f"{scenario.name}_short_borrow_bps_per_day"
        ] = scenario.short_borrow_bps_per_day

        contribution_column = (
            f"{scenario.name}_portfolio_contribution_pct"
        )
        stats = summarize_values(
            portfolio_frame[contribution_column]
        )
        for name, value in stats.items():
            overall[
                f"{scenario.name}_{name}"
            ] = value

        terminal = portfolio_terminal_return_pct(
            portfolio_frame,
            config,
            f"{scenario.name}_net_return_pct",
        )
        overall[
            f"{scenario.name}_terminal_return_pct"
        ] = terminal
        overall[
            f"{scenario.name}_cagr_pct"
        ] = cagr_pct(
            terminal,
            years,
        )

    rows.append(overall)

    for (
        symbol_a,
        symbol_b,
    ), fraction in allocations.items():
        pair_trades = portfolio_frame[
            (portfolio_frame["symbol_a"] == symbol_a)
            & (portfolio_frame["symbol_b"] == symbol_b)
            & (portfolio_frame["status"] == "closed")
        ].sort_values("entry_date")

        row = {
            "scope": f"{symbol_a}/{symbol_b}",
            "portfolio_mode": config.portfolio_mode,
            "trade_count": len(pair_trades),
            "capital_fraction": fraction,
            "primary_cost_scenario": (
                config.primary_cost_scenario
            ),
        }

        gross_stats = summarize_values(
            pair_trades["gross_return_pct"]
        )
        for name, value in gross_stats.items():
            row[f"gross_{name}"] = value

        gross_sleeve_return = (
            compounded_growth(
                pair_trades["gross_return_pct"]
            ) - 1.0
        ) * 100.0
        row[
            "gross_sleeve_return_pct"
        ] = gross_sleeve_return
        row[
            "gross_portfolio_terminal_contribution_pct"
        ] = (
            fraction * gross_sleeve_return
        )

        for scenario in config.cost_scenarios:
            row[
                f"{scenario.name}_transaction_cost_bps_per_turnover"
            ] = scenario.transaction_cost_bps_per_turnover
            row[
                f"{scenario.name}_short_borrow_bps_per_day"
            ] = scenario.short_borrow_bps_per_day

            return_column = (
                f"{scenario.name}_net_return_pct"
            )
            stats = summarize_values(
                pair_trades[return_column]
            )
            for name, value in stats.items():
                row[
                    f"{scenario.name}_{name}"
                ] = value

            sleeve_return = (
                compounded_growth(
                    pair_trades[return_column]
                ) - 1.0
            ) * 100.0
            row[
                f"{scenario.name}_sleeve_return_pct"
            ] = sleeve_return
            row[
                f"{scenario.name}_portfolio_terminal_contribution_pct"
            ] = (
                fraction * sleeve_return
            )

        rows.append(row)

    return pd.DataFrame(rows)


def print_summary(
    summary: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    config: PairStrategyConfig,
):
    primary = config.primary_cost_scenario

    print(
        "\n=== Pair別成績 "
        "（2016–2020 development）==="
    )

    columns = [
        "symbol_a",
        "symbol_b",
        f"{primary}_trade_count",
        f"{primary}_average_pct",
        f"{primary}_median_pct",
        f"{primary}_win_rate",
        f"{primary}_t_value",
        f"{primary}_worst_trade_pct",
    ]
    print(
        summary[columns].to_string(
            index=False,
        )
    )

    print(
        "\n=== 50/50固定Pair Sleeves ==="
    )
    portfolio_all = portfolio_summary[
        portfolio_summary["scope"]
        == "portfolio_all"
    ]

    columns = [
        "scope",
        "trade_count",
        f"{primary}_sum_pct",
        f"{primary}_terminal_return_pct",
        f"{primary}_cagr_pct",
        "stress_terminal_return_pct",
        "stress_cagr_pct",
    ]
    print(
        portfolio_all[columns].to_string(
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
        config_path,
    )
    config = PairStrategyConfig.from_config_data(
        config_data
    )

    print("=== Pair Strategy FINAL OOS ===")
    print(
        "評価期間: "
        f"{config.evaluation_period[0]}～"
        f"{config.evaluation_period[1]}"
    )
    print(
        "hedge推定期間: "
        f"{config.hedge_fit_period[0]}～"
        f"{config.hedge_fit_period[1]}"
    )
    print(
        "固定ルール: "
        f"{config.z_lookback}日z-score / "
        f"{config.entry_z:g}σ / "
        "zero cross / "
        f"最大{config.max_hold_days}営業日 / "
        f"翌{config.entry_delay_days}営業日終値entry"
    )
    print(
        "FINAL OOS: 2021-2025のみを一度だけ評価します。"
    )
    print(
        "2026年は今回読みません。将来のforward期間として残します。"
    )
    print(
        "Return basis: 株式分割調整済み終値の価格リターン。"
        "配当はデータに無いため含めません。"
    )
    print("固定コスト:")
    for scenario in config.cost_scenarios:
        primary_mark = (
            " [PRIMARY]"
            if scenario.name
            == config.primary_cost_scenario
            else ""
        )
        print(
            f"  {scenario.name}: "
            f"取引 {scenario.transaction_cost_bps_per_turnover:g}bps"
            f"/turnover, "
            f"空売り {scenario.short_borrow_bps_per_day:g}bps/day"
            f"{primary_mark}"
        )
    print(
        "Portfolio: 本命2組へ50%ずつ固定配分。"
        "両方のsignalを同時に採用可能。"
    )

    trade_rows = []

    for symbol_a, symbol_b in config.pairs:
        print(
            f"\n{symbol_a} / {symbol_b}"
        )

        frame, alpha, beta = build_pair_frame(
            symbol_a,
            symbol_b,
            config,
            data_folder,
        )
        print(
            f"  fixed alpha={alpha:.6f}, "
            f"beta={beta:.6f}"
        )

        trades = build_trades_for_pair(
            symbol_a,
            symbol_b,
            frame,
            alpha,
            beta,
            config,
        )
        trade_rows.extend(trades)

    trade_frame = pd.DataFrame(
        trade_rows
    )
    summary_frame = build_summary(
        trade_frame,
        config,
    )
    portfolio_frame = build_portfolio(
        trade_frame,
        config,
    )
    portfolio_summary_frame = (
        build_portfolio_summary(
            portfolio_frame,
            config,
        )
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
    portfolio_path = (
        save_dir / PORTFOLIO_OUTPUT_FILE
    )
    portfolio_summary_path = (
        save_dir / PORTFOLIO_SUMMARY_OUTPUT_FILE
    )

    trade_frame.to_csv(
        trade_path,
        **csv_options,
    )
    summary_frame.to_csv(
        summary_path,
        **csv_options,
    )
    portfolio_frame.to_csv(
        portfolio_path,
        **csv_options,
    )
    portfolio_summary_frame.to_csv(
        portfolio_summary_path,
        **csv_options,
    )

    print_summary(
        summary_frame,
        portfolio_summary_frame,
        config,
    )

    print("\n出力:")
    print(f"  {trade_path}")
    print(f"  {summary_path}")
    print(f"  {portfolio_path}")
    print(f"  {portfolio_summary_path}")
    print(
        "\n最終OOSを実行しました。"
        "この結果を見た後は売買ルールを変更して"
        "同じ2021-2025を再評価しないでください。"
    )

    return (
        trade_path,
        summary_path,
        portfolio_path,
        portfolio_summary_path,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Pair Research本命を、"
            "固定した単純売買ルールで検証する。"
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
