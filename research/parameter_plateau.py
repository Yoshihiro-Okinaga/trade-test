import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CENTER_MIN_TRADES = 150
IS_MIN_T = 2.0
NEIGHBOR_MIN_T = 1.0
DEVELOPMENT_MIN_AVERAGE = 0.0
ROUND_DIGITS = 9

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
    "trade_count",
    "average_pct",
    "t_value",
]


def validate_ranking(frame: pd.DataFrame, label: str):
    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{label} に必要な列がありません: {missing}"
        )

    duplicated = frame.duplicated(TASK_COLUMNS, keep=False)
    if duplicated.any():
        raise ValueError(
            f"{label} に同じStrategyTaskが重複しています。"
        )


def adjacent_values(values: list[float], center: float):
    index = values.index(center)
    start = max(0, index - 1)
    end = min(len(values), index + 2)
    return values[start:end]


def build_lookup(frame: pd.DataFrame):
    return {
        tuple(row[column] for column in TASK_COLUMNS): row
        for _, row in frame.iterrows()
    }


def select_centers(is_ranking: pd.DataFrame):
    eligible = is_ranking[
        is_ranking["trade_count"] >= CENTER_MIN_TRADES
    ].copy()

    sort_columns = ["t_value"] + TASK_COLUMNS
    ascending = [False] + [True] * len(TASK_COLUMNS)

    eligible = eligible.sort_values(
        sort_columns,
        ascending=ascending,
        kind="mergesort",
    )

    centers = (
        eligible
        .groupby(["target", "ref"], sort=False)
        .head(1)
        .copy()
        .reset_index(drop=True)
    )
    return centers


def build_local_metrics(
    center: pd.Series,
    lookup: dict,
    sma_grid: list[int],
    threshold_grids: dict[str, list[float]],
):
    signal_type = str(center["signal_type"])
    sma_period = int(center["sma_period"])
    threshold = float(center["threshold_width"])

    sma_values = adjacent_values(sma_grid, sma_period)
    threshold_values = adjacent_values(
        threshold_grids[signal_type],
        threshold,
    )

    expected = []
    for neighbor_threshold in threshold_values:
        for neighbor_sma in sma_values:
            if (
                neighbor_threshold == threshold
                and neighbor_sma == sma_period
            ):
                continue
            expected.append((neighbor_threshold, neighbor_sma))

    values = []
    for neighbor_threshold, neighbor_sma in expected:
        key = (
            center["target"],
            center["ref"],
            signal_type,
            bool(center["counter_trade"]),
            bool(center["use_excess_return"]),
            float(neighbor_threshold),
            int(center["hold_days"]),
            int(center["start_days"]),
            int(neighbor_sma),
        )
        row = lookup.get(key)
        if row is not None:
            values.append(float(row["t_value"]))

    expected_count = len(expected)
    valid_count = len(values)

    return {
        "neighbor_expected_count": expected_count,
        "neighbor_valid_count": valid_count,
        "neighbor_coverage_ratio": (
            valid_count / expected_count
            if expected_count
            else 1.0
        ),
        "neighbor_mean_t": (
            float(np.mean(values))
            if values
            else np.nan
        ),
        "neighbor_worst_t": (
            float(np.min(values))
            if values
            else np.nan
        ),
    }


def attach_plateau_metrics(
    is_ranking: pd.DataFrame,
    centers: pd.DataFrame,
):
    lookup = build_lookup(is_ranking)

    sma_grid = sorted(
        int(value)
        for value in is_ranking["sma_period"].dropna().unique()
    )

    threshold_grids = {}
    for signal_type, frame in is_ranking.groupby("signal_type"):
        threshold_grids[str(signal_type)] = sorted(
            float(value)
            for value in frame["threshold_width"].dropna().unique()
        )

    rows = []
    for _, center in centers.iterrows():
        rows.append(
            build_local_metrics(
                center,
                lookup,
                sma_grid,
                threshold_grids,
            )
        )

    return pd.concat(
        [centers, pd.DataFrame(rows)],
        axis=1,
    )


def attach_development(
    centers: pd.DataFrame,
    development: pd.DataFrame,
):
    development_columns = TASK_COLUMNS + [
        "trade_count",
        "average_pct",
        "t_value",
        "win_rate",
    ]
    development_columns = [
        column
        for column in development_columns
        if column in development.columns
    ]

    return centers.merge(
        development[development_columns],
        on=TASK_COLUMNS,
        how="left",
        suffixes=("_is", "_development"),
        validate="one_to_one",
    )


def run(
    is_ranking_path: Path,
    development_ranking_path: Path,
    output_dir: Path,
):
    is_ranking = pd.read_csv(is_ranking_path)
    development = pd.read_csv(development_ranking_path)

    validate_ranking(is_ranking, "IS ranking")
    validate_ranking(development, "development ranking")

    centers = select_centers(is_ranking)
    centers = attach_plateau_metrics(is_ranking, centers)
    result = attach_development(centers, development)

    result["is_self_pair"] = result["target"] == result["ref"]
    result["rule_b_pass"] = (
        (result["trade_count_is"] >= CENTER_MIN_TRADES)
        & (result["t_value_is"] >= IS_MIN_T)
        & (result["neighbor_worst_t"] >= NEIGHBOR_MIN_T)
    )
    result["development_pass"] = (
        result["average_pct_development"]
        > DEVELOPMENT_MIN_AVERAGE
    )
    result["final_candidate"] = (
        ~result["is_self_pair"]
        & result["rule_b_pass"]
        & result["development_pass"]
    )

    candidates = result[result["final_candidate"]].copy()
    candidates = candidates.sort_values(
        ["t_value_is", "target", "ref"],
        ascending=[False, True, True],
        kind="mergesort",
    )

    summary = pd.DataFrame([
        {
            "center_count": len(result),
            "cross_market_center_count": int((~result["is_self_pair"]).sum()),
            "rule_b_pass_count": int(
                ((~result["is_self_pair"]) & result["rule_b_pass"]).sum()
            ),
            "final_candidate_count": len(candidates),
            "center_min_trades": CENTER_MIN_TRADES,
            "is_min_t": IS_MIN_T,
            "neighbor_min_t": NEIGHBOR_MIN_T,
            "development_min_average_pct": DEVELOPMENT_MIN_AVERAGE,
        }
    ])

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    result.to_csv(
        output_dir / "parameter_plateau_centers.csv",
        **csv_options,
    )
    candidates.to_csv(
        output_dir / "parameter_plateau_candidates.csv",
        **csv_options,
    )
    summary.to_csv(
        output_dir / "parameter_plateau_summary.csv",
        **csv_options,
    )

    print("=== Parameter Plateau ===")
    print(f"centers: {len(result)}")
    print(
        "Rule B pass: "
        f"{int(((~result['is_self_pair']) & result['rule_b_pass']).sum())}"
    )
    print(f"development pass candidates: {len(candidates)}")
    print(f"output: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "2001-2015 ISと2016-2020 developmentの"
            "trade_ranking_full.csvからParameter Plateau候補を作る。"
        )
    )
    parser.add_argument(
        "--is-ranking",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--development-ranking",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results") / "parameter_plateau",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        is_ranking_path=args.is_ranking,
        development_ranking_path=args.development_ranking,
        output_dir=args.output_dir,
    )
