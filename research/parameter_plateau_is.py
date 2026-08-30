import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CENTER_MIN_TRADES = 150
SMA_GRID = [10, 15, 50, 100, 200]
THRESHOLD_GRID = {
    "change": [1.0],
    "sma": [1.0],
    "bb": [1.0, 1.5, 2.0, 2.5, 3.0],
    "di": [20.0],
    "stoch": [30.0],
}

KEY_COLUMNS = [
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


def adjacent_values(grid, value):
    index = grid.index(value)
    return grid[
        max(0, index - 1):
        min(len(grid), index + 2)
    ]


def build_lookup(frame):
    lookup = {}

    for _, row in frame.iterrows():
        key = tuple(
            row[column]
            for column in KEY_COLUMNS
        )
        lookup[key] = row

    return lookup


def local_metrics(
    center,
    lookup,
):
    signal_type = center["signal_type"]
    sma_period = int(
        center["sma_period"]
    )
    threshold = float(
        center["threshold_width"]
    )

    sma_values = adjacent_values(
        SMA_GRID,
        sma_period,
    )
    threshold_values = adjacent_values(
        THRESHOLD_GRID[signal_type],
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

            expected.append(
                (
                    float(neighbor_threshold),
                    int(neighbor_sma),
                )
            )

    values = []

    for neighbor_threshold, neighbor_sma in expected:
        key = (
            center["target"],
            center["ref"],
            signal_type,
            bool(
                center["counter_trade"]
            ),
            bool(
                center["use_excess_return"]
            ),
            neighbor_threshold,
            int(center["hold_days"]),
            int(center["start_days"]),
            neighbor_sma,
        )

        row = lookup.get(key)

        if row is not None:
            values.append(
                float(row["t_value"])
            )

    expected_count = len(expected)
    valid_count = len(values)

    if expected_count == 0:
        coverage = 1.0
        positive_ratio = 1.0
        t_ge_1_ratio = 1.0
    else:
        coverage = (
            valid_count
            / expected_count
        )
        positive_ratio = (
            sum(
                value > 0
                for value in values
            )
            / expected_count
        )
        t_ge_1_ratio = (
            sum(
                value >= 1
                for value in values
            )
            / expected_count
        )

    return {
        "neighbor_expected_count": (
            expected_count
        ),
        "neighbor_valid_count": (
            valid_count
        ),
        "neighbor_coverage_ratio": (
            coverage
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
        "neighbor_positive_ratio_expected": (
            positive_ratio
        ),
        "neighbor_t_ge_1_ratio_expected": (
            t_ge_1_ratio
        ),
    }


def run(
    ranking_path,
    output_path,
):
    ranking = pd.read_csv(
        ranking_path
    )

    eligible = ranking[
        ranking["trade_count"]
        >= CENTER_MIN_TRADES
    ].copy()

    best_indexes = (
        eligible
        .groupby(
            ["target", "ref"]
        )["t_value"]
        .idxmax()
    )

    centers = ranking.loc[
        best_indexes
    ].copy()
    centers = centers.reset_index(
        drop=True
    )

    lookup = build_lookup(
        ranking
    )

    local_rows = []

    for _, center in centers.iterrows():
        local_rows.append(
            local_metrics(
                center,
                lookup,
            )
        )

    centers = pd.concat(
        [
            centers,
            pd.DataFrame(
                local_rows
            ),
        ],
        axis=1,
    )

    signal_best = (
        eligible
        .groupby(
            [
                "target",
                "ref",
                "signal_type",
            ]
        )["t_value"]
        .max()
        .unstack()
    )

    signal_support = pd.DataFrame({
        "signal_type_support_t_ge_1": (
            signal_best >= 1.0
        ).sum(axis=1),
        "signal_type_support_t_ge_2": (
            signal_best >= 2.0
        ).sum(axis=1),
    }).reset_index()

    pair_support = (
        eligible
        .groupby(
            ["target", "ref"]
        )
        .agg(
            eligible_task_count=(
                "t_value",
                "size",
            ),
            eligible_task_positive_ratio=(
                "t_value",
                lambda values: (
                    values > 0
                ).mean(),
            ),
            eligible_task_t_ge_1_ratio=(
                "t_value",
                lambda values: (
                    values >= 1
                ).mean(),
            ),
            eligible_mean_t=(
                "t_value",
                "mean",
            ),
            eligible_median_t=(
                "t_value",
                "median",
            ),
        )
        .reset_index()
    )

    centers = centers.merge(
        signal_support,
        on=["target", "ref"],
        how="left",
    )
    centers = centers.merge(
        pair_support,
        on=["target", "ref"],
        how="left",
    )

    centers["is_self_pair"] = (
        centers["target"]
        == centers["ref"]
    )

    centers.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        float_format="%.9f",
        lineterminator="\r\n",
    )

    print(
        f"output: {output_path}"
    )
    print(
        f"pairs: {len(centers)}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "2001-2015 full rankingから"
            "Parameter Plateau用の"
            "中心戦略と近傍指標を作る。"
        )
    )
    parser.add_argument(
        "ranking",
        type=Path,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "parameter_plateau_is_centers.csv"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        ranking_path=args.ranking,
        output_path=args.output,
    )
