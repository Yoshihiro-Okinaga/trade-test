import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def build_correlations(
    analysis: pd.DataFrame,
) -> pd.DataFrame:
    metrics = [
        "t_value_is",
        "neighbor_mean_t",
        "neighbor_worst_t",
        "neighbor_coverage_ratio",
        "neighbor_positive_ratio_expected",
        "neighbor_t_ge_1_ratio_expected",
        "signal_type_support_t_ge_1",
        "signal_type_support_t_ge_2",
        "eligible_task_positive_ratio",
        "eligible_task_t_ge_1_ratio",
        "eligible_mean_t",
        "eligible_median_t",
        "positive_year_ratio_is",
    ]

    development_metrics = [
        "average_pct_dev",
        "t_value_dev",
        "win_rate_dev",
        "positive_year_ratio_dev",
    ]

    rows = []

    for metric in metrics:
        for development_metric in development_metrics:
            frame = analysis[
                [metric, development_metric]
            ].dropna()

            rows.append({
                "metric": metric,
                "development_metric": development_metric,
                "count": len(frame),
                "pearson": frame[metric].corr(
                    frame[development_metric],
                    method="pearson",
                ),
                "spearman": frame[metric].corr(
                    frame[development_metric],
                    method="spearman",
                ),
            })

    return pd.DataFrame(rows)


def build_median_splits(
    analysis: pd.DataFrame,
) -> pd.DataFrame:
    high_is = analysis[
        analysis["t_value_is"] >= 2.0
    ].copy()

    split_metrics = [
        "t_value_is",
        "neighbor_mean_t",
        "neighbor_worst_t",
        "signal_type_support_t_ge_1",
        "eligible_task_t_ge_1_ratio",
        "positive_year_ratio_is",
    ]

    rows = []

    for metric in split_metrics:
        median_value = float(
            high_is[metric].median()
        )

        groups = [
            (
                "high_half",
                high_is[
                    high_is[metric]
                    >= median_value
                ],
            ),
            (
                "low_half",
                high_is[
                    high_is[metric]
                    < median_value
                ],
            ),
        ]

        for group_name, frame in groups:
            rows.append({
                "is_filter": "t_value_is >= 2.0",
                "split_metric": metric,
                "split_value_is_median": median_value,
                "group": group_name,
                "count": len(frame),
                "development_positive_rate": (
                    frame["average_pct_dev"] > 0
                ).mean(),
                "development_average_pct": (
                    frame["average_pct_dev"].mean()
                ),
                "development_t_value_mean": (
                    frame["t_value_dev"].mean()
                ),
                "development_win_rate_mean": (
                    frame["win_rate_dev"].mean()
                ),
            })

    return pd.DataFrame(rows)


def build_neighbor_thresholds(
    analysis: pd.DataFrame,
) -> pd.DataFrame:
    high_is = analysis[
        analysis["t_value_is"] >= 2.0
    ].copy()

    rows = [{
        "rule": "IS t >= 2.0",
        "count": len(high_is),
        "development_positive_rate": (
            high_is["average_pct_dev"] > 0
        ).mean(),
        "development_average_pct": (
            high_is["average_pct_dev"].mean()
        ),
        "development_t_value_mean": (
            high_is["t_value_dev"].mean()
        ),
    }]

    for threshold in [0.0, 0.5, 1.0, 1.5]:
        frame = high_is[
            high_is["neighbor_worst_t"]
            >= threshold
        ]

        rows.append({
            "rule": (
                "IS t >= 2.0 and "
                f"neighbor_worst_t >= {threshold:.1f}"
            ),
            "count": len(frame),
            "development_positive_rate": (
                frame["average_pct_dev"] > 0
            ).mean(),
            "development_average_pct": (
                frame["average_pct_dev"].mean()
            ),
            "development_t_value_mean": (
                frame["t_value_dev"].mean()
            ),
        })

    return pd.DataFrame(rows)


def run(
    is_centers_path: Path,
    development_ranking_path: Path,
    output_dir: Path,
):
    is_centers = pd.read_csv(
        is_centers_path
    )
    development = pd.read_csv(
        development_ranking_path
    )

    keys = [
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

    development_columns = keys + [
        "trade_count",
        "average_pct",
        "std_pct",
        "t_value",
        "win_rate",
        "positive_year_ratio",
        "worst_year_profit",
        "average_long_pct",
        "average_short_pct",
    ]

    merged = is_centers.merge(
        development[development_columns],
        on=keys,
        how="left",
        suffixes=("_is", "_dev"),
        validate="one_to_one",
    )

    missing = merged[
        merged["average_pct_dev"].isna()
    ]

    if not missing.empty:
        raise RuntimeError(
            "2016-2020 developmentで"
            f"{len(missing)}個の中心戦略が"
            "見つかりません。"
        )

    analysis = merged[
        ~merged["is_self_pair"]
    ].copy()

    correlations = build_correlations(
        analysis
    )
    median_splits = build_median_splits(
        analysis
    )
    thresholds = build_neighbor_thresholds(
        analysis
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    options = dict(
        index=False,
        encoding="utf-8",
        float_format="%.9f",
        lineterminator="\r\n",
    )

    analysis.to_csv(
        output_dir
        / "parameter_plateau_development_audit.csv",
        **options,
    )
    correlations.to_csv(
        output_dir
        / "parameter_plateau_correlations.csv",
        **options,
    )
    median_splits.to_csv(
        output_dir
        / "parameter_plateau_is_t_ge_2_median_splits.csv",
        **options,
    )
    thresholds.to_csv(
        output_dir
        / "parameter_plateau_neighbor_worst_thresholds.csv",
        **options,
    )

    print("=== Parameter Plateau Development Analysis ===")
    print(f"cross-market pairs: {len(analysis)}")

    base = thresholds[
        thresholds["rule"]
        == "IS t >= 2.0"
    ].iloc[0]

    robust = thresholds[
        thresholds["rule"]
        == (
            "IS t >= 2.0 and "
            "neighbor_worst_t >= 1.0"
        )
    ].iloc[0]

    print(
        "Rule A:",
        f"n={int(base['count'])}",
        f"positive={base['development_positive_rate'] * 100:.1f}%",
        f"avg={base['development_average_pct']:+.3f}%",
    )
    print(
        "Rule B:",
        f"n={int(robust['count'])}",
        f"positive={robust['development_positive_rate'] * 100:.1f}%",
        f"avg={robust['development_average_pct']:+.3f}%",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "2001-2015のParameter Plateau中心戦略を、"
            "2016-2020 rankingへ固定照合して"
            "development成績との関係を分析する。"
        )
    )
    parser.add_argument(
        "--is-centers",
        type=Path,
        required=True,
        help=(
            "parameter_plateau_is_centers.csv"
        ),
    )
    parser.add_argument(
        "--development-ranking",
        type=Path,
        required=True,
        help=(
            "2016-2020のtrade_ranking_full.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "plateau_analysis_results"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        is_centers_path=args.is_centers,
        development_ranking_path=(
            args.development_ranking
        ),
        output_dir=args.output_dir,
    )
