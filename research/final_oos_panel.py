import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import backtest
import market_data
from research import development_panel


ROUND_DIGITS = 9
FINAL_START_YEAR = 2021
FINAL_END_YEAR = 2025
EXPECTED_DEVELOPMENT_START_YEAR = 2016
EXPECTED_DEVELOPMENT_END_YEAR = 2020


def normalize_bool_value(value, label: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)

    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"{label} をboolへ変換できません: {value!r}")


def validate_development_pass(
    summary_path: Path,
    panel: pd.DataFrame,
    target: str,
    ref: str,
) -> pd.Series:
    summary = pd.read_csv(summary_path)
    if len(summary) != 1:
        raise ValueError(
            f"{summary_path} は1行のDevelopment summaryである必要があります。"
        )

    row = summary.iloc[0]
    required_columns = [
        "development_start_year",
        "development_end_year",
        "required_task_count",
        "evaluated_task_count",
        "min_positive_task_ratio",
        "positive_task_count",
        "required_positive_task_count",
        "panel_average_pct",
        "development_pass",
        "target",
        "ref",
    ]
    missing = [column for column in required_columns if column not in summary.columns]
    if missing:
        raise ValueError(
            f"{summary_path} に必要な列がありません: {missing}"
        )

    if str(row["target"]) != target or str(row["ref"]) != ref:
        raise ValueError(
            "Development summaryのpairがfinal対象と一致しません。"
            f" summary={row['target']} <- {row['ref']}, "
            f"final={target} <- {ref}"
        )

    start_year = int(row["development_start_year"])
    end_year = int(row["development_end_year"])
    if (
        start_year != EXPECTED_DEVELOPMENT_START_YEAR
        or end_year != EXPECTED_DEVELOPMENT_END_YEAR
    ):
        raise ValueError(
            "Development期間が固定条件と一致しません。"
            f" expected={EXPECTED_DEVELOPMENT_START_YEAR}-"
            f"{EXPECTED_DEVELOPMENT_END_YEAR}, "
            f"actual={start_year}-{end_year}"
        )

    task_count = len(panel)
    required_task_count = int(row["required_task_count"])
    evaluated_task_count = int(row["evaluated_task_count"])
    if required_task_count != task_count or evaluated_task_count != task_count:
        raise ValueError(
            "Development summaryのTask数が固定パネルと一致しません。"
            f" panel={task_count}, required={required_task_count}, "
            f"evaluated={evaluated_task_count}"
        )

    ratio = float(row["min_positive_task_ratio"])
    expected_ratio = development_panel.MIN_POSITIVE_TASK_RATIO
    if not np.isclose(ratio, expected_ratio, atol=1e-12, rtol=0):
        raise ValueError(
            "Development gateのpositive比率が現在の固定条件と一致しません。"
            f" expected={expected_ratio}, actual={ratio}"
        )

    expected_positive_count = math.ceil(expected_ratio * task_count)
    actual_required_positive = int(row["required_positive_task_count"])
    if actual_required_positive != expected_positive_count:
        raise ValueError(
            "Development gateの必要positive数が固定条件と一致しません。"
            f" expected={expected_positive_count}, "
            f"actual={actual_required_positive}"
        )

    development_result_columns = [
        "development_average_pct",
        "development_positive",
    ]
    missing_result_columns = [
        column for column in development_result_columns
        if column not in panel.columns
    ]
    if missing_result_columns:
        raise ValueError(
            "Development Task結果が不足しています: "
            f"{missing_result_columns}"
        )

    task_gate = development_panel.evaluate_gate(panel)
    if not task_gate["development_pass"]:
        raise ValueError(
            "development_panel_tasks.csvを再計算するとREJECTです。"
            " summaryだけを信頼してfinalへ進めません。"
        )

    summary_pass = normalize_bool_value(
        row["development_pass"],
        "development_pass",
    )
    if not summary_pass:
        raise ValueError(
            "Development REJECTのパネルはfinal OOSへ進めません。"
        )

    for key in [
        "positive_task_count",
        "required_positive_task_count",
    ]:
        if int(row[key]) != int(task_gate[key]):
            raise ValueError(
                f"Development summaryとTask結果の{key}が一致しません。"
                f" summary={int(row[key])}, tasks={int(task_gate[key])}"
            )

    if not np.isclose(
        float(row["panel_average_pct"]),
        float(task_gate["panel_average_pct"]),
        atol=1e-9,
        rtol=0,
    ):
        raise ValueError(
            "Development summaryとTask結果のpanel_average_pctが一致しません。"
        )

    return row


def filter_final_oos_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame()

    start = pd.Timestamp(FINAL_START_YEAR, 1, 1)
    end = pd.Timestamp(FINAL_END_YEAR, 12, 31)

    result = trades.copy()
    result["entry_date"] = pd.to_datetime(result["entry_date"])
    result["exit_date"] = pd.to_datetime(result["exit_date"])

    # finalでもentry/exitの両方を期間内に完結させる。
    # 2025年末エントリーが2026年価格を使うことを防ぐ。
    filtered = result[
        (result["entry_date"] >= start)
        & (result["entry_date"] <= end)
        & (result["exit_date"] >= start)
        & (result["exit_date"] <= end)
    ].copy()

    # calc_trade_results() のattrsにはDataFrameが入り、pandas.concat時の
    # attrs比較で例外になる。final明細では使わないため明示的に捨てる。
    filtered.attrs.clear()
    return filtered


def summarize_task_trades(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "final_oos_trade_count": 0,
            "final_oos_long_count": 0,
            "final_oos_short_count": 0,
            "final_oos_win_rate": np.nan,
            "final_oos_average_pct": np.nan,
            "final_oos_median_pct": np.nan,
            "final_oos_std_pct": np.nan,
            "final_oos_t_value": np.nan,
            "final_oos_min_entry_date": "",
            "final_oos_max_exit_date": "",
            "final_oos_positive": False,
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
        "final_oos_trade_count": trade_count,
        "final_oos_long_count": int((trades["position"] == "long").sum()),
        "final_oos_short_count": int((trades["position"] == "short").sum()),
        "final_oos_win_rate": float((profit_pct > 0).mean() * 100),
        "final_oos_average_pct": average_pct,
        "final_oos_median_pct": median_pct,
        "final_oos_std_pct": std_pct,
        "final_oos_t_value": t_value,
        "final_oos_min_entry_date": trades["entry_date"].min().date().isoformat(),
        "final_oos_max_exit_date": trades["exit_date"].max().date().isoformat(),
        "final_oos_positive": bool(average_pct > 0),
    }


def evaluate_gate(results: pd.DataFrame) -> dict:
    required_task_count = len(results)
    required_positive_task_count = math.ceil(
        development_panel.MIN_POSITIVE_TASK_RATIO * required_task_count
    )

    state_mask = results["signal_class"] == "state"
    event_mask = results["signal_class"] == "event"
    state_task_count = int(state_mask.sum())
    event_task_count = int(event_mask.sum())

    all_tasks_evaluated = bool(
        required_task_count > 0
        and results["final_oos_average_pct"].notna().all()
    )
    positive_task_count = int(results["final_oos_positive"].sum())
    state_positive_count = int(
        results.loc[state_mask, "final_oos_positive"].sum()
    )
    event_positive_count = int(
        results.loc[event_mask, "final_oos_positive"].sum()
    )

    panel_average_pct = (
        float(results["final_oos_average_pct"].mean())
        if all_tasks_evaluated
        else np.nan
    )

    enough_positive_tasks = (
        positive_task_count >= required_positive_task_count
    )
    state_confirmation = (
        state_task_count > 0
        and state_positive_count >= development_panel.MIN_POSITIVE_STATE
    )
    event_confirmation = (
        event_task_count > 0
        and event_positive_count >= development_panel.MIN_POSITIVE_EVENT
    )
    positive_panel_average = bool(
        np.isfinite(panel_average_pct) and panel_average_pct > 0
    )

    final_oos_pass = bool(
        all_tasks_evaluated
        and enough_positive_tasks
        and state_confirmation
        and event_confirmation
        and positive_panel_average
    )

    return {
        "final_oos_start_year": FINAL_START_YEAR,
        "final_oos_end_year": FINAL_END_YEAR,
        "required_task_count": required_task_count,
        "evaluated_task_count": len(results),
        "all_tasks_evaluated": all_tasks_evaluated,
        "min_positive_task_ratio": development_panel.MIN_POSITIVE_TASK_RATIO,
        "positive_task_count": positive_task_count,
        "required_positive_task_count": required_positive_task_count,
        "positive_task_count_pass": enough_positive_tasks,
        "state_task_count": state_task_count,
        "state_positive_count": state_positive_count,
        "required_state_positive_count": development_panel.MIN_POSITIVE_STATE,
        "state_confirmation_pass": state_confirmation,
        "event_task_count": event_task_count,
        "event_positive_count": event_positive_count,
        "required_event_positive_count": development_panel.MIN_POSITIVE_EVENT,
        "event_confirmation_pass": event_confirmation,
        "panel_average_pct": panel_average_pct,
        "panel_average_positive_pass": positive_panel_average,
        "task_t_value_used_for_gate": False,
        "final_oos_pass": final_oos_pass,
    }


def run(
    development_tasks_path: Path,
    development_summary_path: Path,
    config_path: Path,
    output_dir: Path,
    target: str,
    ref: str,
    data_folder: Path | None,
):
    panel = development_panel.read_frozen_panel(
        development_tasks_path,
        target,
        ref,
    )
    development_summary = validate_development_pass(
        development_summary_path,
        panel,
        target,
        ref,
    )

    config = development_panel.load_base_config(config_path)
    development_panel.validate_global_conditions(config, panel)
    development_panel.prepare_config_for_panel(config, panel, target, ref)

    print("=== Frozen Final OOS Panel ===")
    print(f"pair: {target} <- {ref}")
    print(
        f"period: {FINAL_START_YEAR}-{FINAL_END_YEAR} "
        "(entry/exit both inside period)"
    )
    print(f"tasks: {len(panel)}")
    print("Development PASSを確認しました。")
    print("指標を事前計算しています...", flush=True)

    ref_cache, target_cache = market_data.build_caches(config, data_folder)
    backtest.init_worker(config, ref_cache, target_cache)

    result_rows = []
    trade_frames = []

    for _, row in panel.iterrows():
        task = development_panel.to_strategy_task(row)
        trades, _correlation, other_message = backtest.calc_trade_results(
            config,
            False,
            *task.as_backtest_args(),
        )
        final_trades = filter_final_oos_trades(trades)
        metrics = summarize_task_trades(final_trades)

        result_row = {
            column: row[column]
            for column in development_panel.REQUIRED_COLUMNS
            if column in row.index
        }
        for column in [
            "development_trade_count",
            "development_average_pct",
            "development_t_value",
            "development_positive",
        ]:
            if column in row.index:
                result_row[column] = row[column]
        result_row["other_message"] = other_message
        result_row.update(metrics)
        result_rows.append(result_row)

        if not final_trades.empty:
            detail = final_trades.copy()
            for column in development_panel.TASK_COLUMNS:
                detail[column] = row[column]
            detail["signal_class"] = row["signal_class"]
            trade_frames.append(detail)

        print(
            f"{row['signal_type']}: "
            f"n={metrics['final_oos_trade_count']}, "
            f"avg={metrics['final_oos_average_pct']:.9f}, "
            f"t={metrics['final_oos_t_value']:.6f}"
            if np.isfinite(metrics["final_oos_average_pct"])
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
        "period_boundary_rule": "entry_and_exit_inside_final_oos",
        "source_development_pass": True,
        "source_development_positive_task_count": int(
            development_summary["positive_task_count"]
        ),
        "source_development_panel_average_pct": float(
            development_summary["panel_average_pct"]
        ),
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
        output_dir / "final_oos_panel_tasks.csv",
        **csv_options,
    )
    summary.to_csv(
        output_dir / "final_oos_panel_summary.csv",
        **csv_options,
    )
    trade_details.to_csv(
        output_dir / "final_oos_panel_trades.csv",
        **csv_options,
    )

    print("\n=== Final OOS Gate ===")
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
    print("PASS" if gate["final_oos_pass"] else "REJECT")
    print(f"output: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Development PASS済みの固定StrategyTaskパネルだけを"
            "2021-2025 Final OOSで評価する。"
        )
    )
    parser.add_argument(
        "--development-tasks",
        type=Path,
        required=True,
        help="PASSしたdevelopment_panel_tasks.csvのパス。",
    )
    parser.add_argument(
        "--development-summary",
        type=Path,
        required=True,
        help="PASSしたdevelopment_panel_summary.csvのパス。",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "config.toml",
        help="IS/Developmentと同じ共通売買条件を持つconfig.toml。",
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
        default=PROJECT_DIR / "results" / "final_oos_panel",
        help="結果CSVの出力先。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        development_tasks_path=args.development_tasks,
        development_summary_path=args.development_summary,
        config_path=args.config,
        output_dir=args.output_dir,
        target=args.target,
        ref=args.ref,
        data_folder=args.data_folder,
    )
