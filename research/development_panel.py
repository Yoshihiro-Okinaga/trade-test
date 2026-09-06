import argparse
import math
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import backtest
import backtest_config
import market_data
from backtest_config import SignalType, TradeCodeType
from strategy_task import StrategyTask


ROUND_DIGITS = 9
DEVELOPMENT_START_YEAR = 2016
DEVELOPMENT_END_YEAR = 2020
MIN_POSITIVE_TASK_RATIO = 0.75
MIN_POSITIVE_STATE = 1
MIN_POSITIVE_EVENT = 1
REQUIRE_STATE_AND_EVENT = True

# 今回のIS探索で固定した共通実験条件。
# StrategyTask外の設定が後で変わっても、黙って別条件を評価しないため検証する。
EXPECTED_NO_OVERLAP = False
EXPECTED_EXTRA_COST_PCT = 0.0
EXPECTED_FILTER_SIGNAL_TYPE = ""
EXPECTED_SIGNAL_CENTERS = {
    "change": 0.0,
    "sma": 0.0,
    "bb": 0.0,
    "macd": 0.0,
    "rsi": 50.0,
    "di": 0.0,
    "stoch": 50.0,
    "streak": 0.0,
    "breakout": 0.0,
}

TASK_COLUMNS = [
    "target",
    "ref",
    "signal_type",
    "counter_trade",
    "use_excess_return",
    "threshold_width",
    "hold_days",
    "start_days",
    "sma_period",
]

REQUIRED_COLUMNS = TASK_COLUMNS + [
    "signal_class",
    "signal_direction_status",
    "discovery_trade_count",
    "discovery_average_pct",
    "discovery_t_value",
]


def normalize_bool(series: pd.Series, column: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)

    text = series.astype(str).str.strip().str.lower()
    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }
    invalid = ~text.isin(mapping)
    if invalid.any():
        examples = sorted(text[invalid].unique())[:5]
        raise ValueError(
            f"{column} にboolへ変換できない値があります: {examples}"
        )
    return text.map(mapping).astype(bool)


def read_frozen_panel(
    tasks_path: Path,
    target: str,
    ref: str,
) -> pd.DataFrame:
    tasks = pd.read_csv(tasks_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in tasks.columns]
    if missing:
        raise ValueError(
            f"{tasks_path} に必要な列がありません: {missing}"
        )

    tasks["counter_trade"] = normalize_bool(
        tasks["counter_trade"], "counter_trade"
    )
    tasks["use_excess_return"] = normalize_bool(
        tasks["use_excess_return"], "use_excess_return"
    )

    for column in [
        "threshold_width",
        "hold_days",
        "start_days",
        "sma_period",
        "discovery_trade_count",
        "discovery_average_pct",
        "discovery_t_value",
    ]:
        tasks[column] = pd.to_numeric(tasks[column], errors="raise")

    panel = tasks[
        (tasks["target"] == target)
        & (tasks["ref"] == ref)
        & (tasks["signal_direction_status"] == "consensus")
    ].copy()

    if panel.empty:
        raise ValueError(
            f"target={target}, ref={ref} のconsensus Taskがありません。"
        )

    duplicated = panel.duplicated(TASK_COLUMNS, keep=False)
    if duplicated.any():
        raise ValueError("同じStrategyTaskが重複しています。")

    state_count = int((panel["signal_class"] == "state").sum())
    event_count = int((panel["signal_class"] == "event").sum())
    unknown_classes = sorted(
        set(panel["signal_class"].dropna()) - {"state", "event"}
    )
    if unknown_classes:
        raise ValueError(
            f"未対応のsignal_classがあります: {unknown_classes}"
        )
    if REQUIRE_STATE_AND_EVENT and (state_count == 0 or event_count == 0):
        raise ValueError(
            "このDevelopment gateはStateとEventの両方を確認するため、"
            "各クラス1本以上が必要です。"
            f" state={state_count}, event={event_count}"
        )

    directions = panel["counter_trade"].unique()
    if len(directions) != 1:
        raise ValueError("固定パネル内でcounter_tradeが一致していません。")

    return panel.sort_values(
        ["signal_class", "signal_type"],
        kind="mergesort",
    ).reset_index(drop=True)


def load_base_config(config_path: Path) -> backtest_config.BackTestConfig:
    try:
        with open(config_path, "rb") as file:
            config_data = tomllib.load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"configが見つかりません: {config_path}"
        ) from exc

    return backtest_config.BackTestConfig(config_data)


def validate_global_conditions(
    config: backtest_config.BackTestConfig,
    panel: pd.DataFrame,
):
    if config.no_overlap != EXPECTED_NO_OVERLAP:
        raise ValueError(
            "IS探索とno_overlapが一致しません。"
            f" expected={EXPECTED_NO_OVERLAP}, actual={config.no_overlap}"
        )

    if not np.isclose(
        config.extra_cost_pct,
        EXPECTED_EXTRA_COST_PCT,
        atol=1e-12,
        rtol=0,
    ):
        raise ValueError(
            "IS探索とextra_cost_pctが一致しません。"
            f" expected={EXPECTED_EXTRA_COST_PCT}, actual={config.extra_cost_pct}"
        )

    if config.filter_signal_type != EXPECTED_FILTER_SIGNAL_TYPE:
        raise ValueError(
            "IS探索とfilter_signal_typeが一致しません。"
            f" expected={EXPECTED_FILTER_SIGNAL_TYPE!r}, "
            f"actual={config.filter_signal_type!r}"
        )

    if config.trade_code_type == TradeCodeType.SAME:
        raise ValueError(
            "cross-marketパネルを評価するため、trade_code_type=sameは使えません。"
        )

    for signal_type in panel["signal_type"].unique():
        expected_center = EXPECTED_SIGNAL_CENTERS.get(str(signal_type))
        if expected_center is None:
            raise ValueError(
                f"固定済みcenter定義がないsignalです: {signal_type}"
            )
        actual_center = config.center_of(SignalType(str(signal_type)))
        if not np.isclose(
            actual_center,
            expected_center,
            atol=1e-12,
            rtol=0,
        ):
            raise ValueError(
                f"{signal_type} のthreshold_centerがIS探索と一致しません。"
                f" expected={expected_center}, actual={actual_center}"
            )


def prepare_config_for_panel(
    config: backtest_config.BackTestConfig,
    panel: pd.DataFrame,
    target: str,
    ref: str,
):
    # build_cachesが固定Taskに必要なものだけを計算するように絞る。
    config.ref_list = [ref]
    config.target_list = [target]
    config.symbol_pairs = [(ref, target)]
    config.start_days_list = sorted(panel["start_days"].astype(int).unique())
    config.sma_period_list = sorted(panel["sma_period"].astype(int).unique())
    config.hold_days_list = sorted(panel["hold_days"].astype(int).unique())


def to_strategy_task(row: pd.Series) -> StrategyTask:
    return StrategyTask(
        ref_name=str(row["ref"]),
        target_name=str(row["target"]),
        signal_type=SignalType(str(row["signal_type"])),
        counter_trade=bool(row["counter_trade"]),
        use_excess_return=bool(row["use_excess_return"]),
        threshold_width=float(row["threshold_width"]),
        hold_days=int(row["hold_days"]),
        start_days=int(row["start_days"]),
        sma_period=int(row["sma_period"]),
    )


def filter_development_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame()

    start = pd.Timestamp(DEVELOPMENT_START_YEAR, 1, 1)
    end = pd.Timestamp(DEVELOPMENT_END_YEAR, 12, 31)

    result = trades.copy()
    result["entry_date"] = pd.to_datetime(result["entry_date"])
    result["exit_date"] = pd.to_datetime(result["exit_date"])

    # entryだけでなくexitもDevelopment内に完結させる。
    # これにより2020年末エントリーが2021年価格を使うことを防ぐ。
    filtered = result[
        (result["entry_date"] >= start)
        & (result["entry_date"] <= end)
        & (result["exit_date"] >= start)
        & (result["exit_date"] <= end)
    ].copy()

    # calc_trade_results() は year_summary を DataFrame.attrs に保持している。
    # pandas.concat() は各DataFrameの attrs 同士を比較するため、attrs 内に
    # DataFrame があると真偽値比較で ValueError になる。Developmentの明細では
    # year_summary を使わないので、期間抽出後にメタデータを明示的に捨てる。
    filtered.attrs.clear()
    return filtered


def summarize_task_trades(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "development_trade_count": 0,
            "development_long_count": 0,
            "development_short_count": 0,
            "development_win_rate": np.nan,
            "development_average_pct": np.nan,
            "development_median_pct": np.nan,
            "development_std_pct": np.nan,
            "development_t_value": np.nan,
            "development_min_entry_date": "",
            "development_max_exit_date": "",
            "development_positive": False,
        }

    profit_pct = pd.to_numeric(trades["profit_pct"], errors="coerce")
    trade_count = len(trades)
    average_pct = float(profit_pct.mean())
    median_pct = float(profit_pct.median())
    std_pct = float(profit_pct.std(ddof=1)) if trade_count > 1 else np.nan
    if trade_count > 1 and np.isfinite(std_pct) and std_pct > 0:
        t_value = average_pct / std_pct * (trade_count ** 0.5)
    else:
        t_value = np.nan

    return {
        "development_trade_count": trade_count,
        "development_long_count": int((trades["position"] == "long").sum()),
        "development_short_count": int((trades["position"] == "short").sum()),
        "development_win_rate": float((profit_pct > 0).mean() * 100),
        "development_average_pct": average_pct,
        "development_median_pct": median_pct,
        "development_std_pct": std_pct,
        "development_t_value": t_value,
        "development_min_entry_date": trades["entry_date"].min().date().isoformat(),
        "development_max_exit_date": trades["exit_date"].max().date().isoformat(),
        "development_positive": bool(average_pct > 0),
    }


def evaluate_gate(results: pd.DataFrame) -> dict:
    required_task_count = len(results)
    required_positive_task_count = math.ceil(
        MIN_POSITIVE_TASK_RATIO * required_task_count
    )

    state_mask = results["signal_class"] == "state"
    event_mask = results["signal_class"] == "event"
    state_task_count = int(state_mask.sum())
    event_task_count = int(event_mask.sum())

    all_tasks_evaluated = bool(
        required_task_count > 0
        and results["development_average_pct"].notna().all()
    )
    positive_task_count = int(results["development_positive"].sum())
    state_positive_count = int(
        results.loc[state_mask, "development_positive"].sum()
    )
    event_positive_count = int(
        results.loc[event_mask, "development_positive"].sum()
    )

    panel_average_pct = (
        float(results["development_average_pct"].mean())
        if all_tasks_evaluated
        else np.nan
    )

    enough_positive_tasks = (
        positive_task_count >= required_positive_task_count
    )
    state_confirmation = (
        state_task_count > 0
        and state_positive_count >= MIN_POSITIVE_STATE
    )
    event_confirmation = (
        event_task_count > 0
        and event_positive_count >= MIN_POSITIVE_EVENT
    )
    positive_panel_average = bool(
        np.isfinite(panel_average_pct) and panel_average_pct > 0
    )

    development_pass = bool(
        all_tasks_evaluated
        and enough_positive_tasks
        and state_confirmation
        and event_confirmation
        and positive_panel_average
    )

    return {
        "development_start_year": DEVELOPMENT_START_YEAR,
        "development_end_year": DEVELOPMENT_END_YEAR,
        "required_task_count": required_task_count,
        "evaluated_task_count": len(results),
        "all_tasks_evaluated": all_tasks_evaluated,
        "min_positive_task_ratio": MIN_POSITIVE_TASK_RATIO,
        "positive_task_count": positive_task_count,
        "required_positive_task_count": required_positive_task_count,
        "positive_task_count_pass": enough_positive_tasks,
        "state_task_count": state_task_count,
        "state_positive_count": state_positive_count,
        "required_state_positive_count": MIN_POSITIVE_STATE,
        "state_confirmation_pass": state_confirmation,
        "event_task_count": event_task_count,
        "event_positive_count": event_positive_count,
        "required_event_positive_count": MIN_POSITIVE_EVENT,
        "event_confirmation_pass": event_confirmation,
        "panel_average_pct": panel_average_pct,
        "panel_average_positive_pass": positive_panel_average,
        "task_t_value_used_for_gate": False,
        "development_pass": development_pass,
    }


def run(
    tasks_path: Path,
    config_path: Path,
    output_dir: Path,
    target: str,
    ref: str,
    data_folder: Path | None,
):
    panel = read_frozen_panel(tasks_path, target, ref)
    config = load_base_config(config_path)
    validate_global_conditions(config, panel)
    prepare_config_for_panel(config, panel, target, ref)

    print("=== Frozen Development Panel ===")
    print(f"pair: {target} <- {ref}")
    print(
        f"period: {DEVELOPMENT_START_YEAR}-{DEVELOPMENT_END_YEAR} "
        "(entry/exit both inside period)"
    )
    print(f"tasks: {len(panel)}")
    print("指標を事前計算しています...", flush=True)

    ref_cache, target_cache = market_data.build_caches(config, data_folder)
    backtest.init_worker(config, ref_cache, target_cache)

    result_rows = []
    trade_frames = []

    for _, row in panel.iterrows():
        task = to_strategy_task(row)
        trades, _correlation, other_message = backtest.calc_trade_results(
            config,
            False,
            *task.as_backtest_args(),
        )
        development_trades = filter_development_trades(trades)
        metrics = summarize_task_trades(development_trades)

        result_row = {
            column: row[column]
            for column in REQUIRED_COLUMNS
            if column in row.index
        }
        result_row["other_message"] = other_message
        result_row.update(metrics)
        result_rows.append(result_row)

        if not development_trades.empty:
            detail = development_trades.copy()
            for column in TASK_COLUMNS:
                detail[column] = row[column]
            detail["signal_class"] = row["signal_class"]
            trade_frames.append(detail)

        print(
            f"{row['signal_type']}: "
            f"n={metrics['development_trade_count']}, "
            f"avg={metrics['development_average_pct']:.9f}, "
            f"t={metrics['development_t_value']:.6f}"
            if np.isfinite(metrics["development_average_pct"])
            else f"{row['signal_type']}: n=0, avg=NaN, t=NaN"
        )

    results = pd.DataFrame(result_rows)
    gate = evaluate_gate(results)
    gate.update({
        "target": target,
        "ref": ref,
        "no_overlap": config.no_overlap,
        "extra_cost_pct": config.extra_cost_pct,
        "filter_signal_type": config.filter_signal_type,
        "period_boundary_rule": "entry_and_exit_inside_development",
    })
    summary = pd.DataFrame([gate])

    if trade_frames:
        trade_details = pd.concat(trade_frames, ignore_index=True)
    else:
        trade_details = pd.DataFrame()

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )
    results.to_csv(
        output_dir / "development_panel_tasks.csv",
        **csv_options,
    )
    summary.to_csv(
        output_dir / "development_panel_summary.csv",
        **csv_options,
    )
    trade_details.to_csv(
        output_dir / "development_panel_trades.csv",
        **csv_options,
    )

    print("\n=== Development Gate ===")
    print(
        f"positive tasks: {gate['positive_task_count']} / "
        f"{gate['required_task_count']}"
    )
    print(
        f"state positive: {gate['state_positive_count']} / "
        f"{gate['state_task_count']}"
    )
    print(
        f"event positive: {gate['event_positive_count']} / "
        f"{gate['event_task_count']}"
    )
    print(f"panel average: {gate['panel_average_pct']:.9f}")
    print("PASS" if gate["development_pass"] else "REJECT")
    print(f"output: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "signal_consensus_tasks.csvで固定したStrategyTaskパネルだけを"
            "2016-2020 Developmentで評価する。"
        )
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        help="signal_consensus_tasks.csv のパス。",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "config.toml",
        help="IS探索と同じ共通売買条件を持つconfig.toml。",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="固定パネルのTarget。",
    )
    parser.add_argument(
        "--ref",
        required=True,
        help="固定パネルのRef。",
    )
    parser.add_argument(
        "--data-folder",
        type=Path,
        default=None,
        help="市場データフォルダ。未指定なら通常のstock-data/Manual。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "results" / "development_panel",
        help="結果CSVの出力先。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        tasks_path=args.tasks,
        config_path=args.config,
        output_dir=args.output_dir,
        target=args.target,
        ref=args.ref,
        data_folder=args.data_folder,
    )
