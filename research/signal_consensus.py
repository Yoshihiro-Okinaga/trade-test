import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROUND_DIGITS = 9

KEY_COLUMNS = [
    "target",
    "ref",
    "signal_type",
    "counter_trade",
    "use_excess_return",
]

REQUIRED_COLUMNS = KEY_COLUMNS + [
    "threshold_width",
    "start_days",
    "sma_period",
    "task_sma_period",
    "signal_class",
    "is_self_pair",
    "is_family_representative",
    "discovery_candidate",
    "discovery_hold",
    "discovery_trade_count",
    "discovery_average_pct",
    "discovery_t_value",
    "response_shape",
]

COMPARE_COLUMNS = [
    "threshold_width",
    "start_days",
    "sma_period",
    "task_sma_period",
    "signal_class",
    "is_self_pair",
    "discovery_candidate",
    "discovery_hold",
    "discovery_trade_count",
    "discovery_average_pct",
    "discovery_t_value",
    "response_shape",
]

EVENT_SHAPES = [
    "fast_decay",
    "short_plateau",
    "persistent",
    "late_extension",
    "mixed",
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


def read_hold_responses(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_csv(
            path,
            usecols=lambda column: column in REQUIRED_COLUMNS,
        )
        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in frame.columns
        ]
        if missing:
            if "task_sma_period" in missing:
                raise ValueError(
                    f"{path} にtask_sma_periodがありません。"
                    "v5のresearch/hold_response.pyでIS rankingから"
                    "hold_response_series.csvを再生成してください。"
                )
            raise ValueError(
                f"{path} に必要な列がありません: {missing}"
            )

        for column in [
            "counter_trade",
            "use_excess_return",
            "is_self_pair",
            "is_family_representative",
            "discovery_candidate",
        ]:
            frame[column] = normalize_bool(frame[column], column)

        for column in [
            "threshold_width",
            "start_days",
            "sma_period",
            "task_sma_period",
            "discovery_hold",
            "discovery_trade_count",
            "discovery_average_pct",
            "discovery_t_value",
        ]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

        frame["signal_type"] = frame["signal_type"].astype(str)
        frame["signal_class"] = frame["signal_class"].astype(str)
        frame["response_shape"] = frame["response_shape"].astype(str)
        frame["source_hold_response"] = str(path)
        frames.append(frame)

    if not frames:
        raise ValueError("hold_response_series.csvを1つ以上指定してください。")

    result = pd.concat(frames, ignore_index=True)
    result = result[result["is_family_representative"]].copy()
    return validate_and_deduplicate(result)


def values_equal(left, right) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if isinstance(left, (float, np.floating)) or isinstance(
        right, (float, np.floating)
    ):
        try:
            return bool(np.isclose(float(left), float(right), atol=1e-12, rtol=0))
        except (TypeError, ValueError):
            return False
    return left == right


def validate_and_deduplicate(frame: pd.DataFrame) -> pd.DataFrame:
    duplicated = frame.duplicated(KEY_COLUMNS, keep=False)
    if not duplicated.any():
        return frame

    duplicate_rows = frame.loc[duplicated].copy()
    conflicts = []
    for key, group in duplicate_rows.groupby(KEY_COLUMNS, dropna=False, sort=False):
        first = group.iloc[0]
        for _, row in group.iloc[1:].iterrows():
            changed = [
                column
                for column in COMPARE_COLUMNS
                if not values_equal(first[column], row[column])
            ]
            if changed:
                conflicts.append((key, changed))
                break

    if conflicts:
        key, changed = conflicts[0]
        raise ValueError(
            "同じsignal family代表が複数入力で異なる結果になっています。"
            f" key={key}, different_columns={changed}。"
            "同じIS条件・同じhold_response設定のCSVだけを組み合わせてください。"
        )

    return frame.drop_duplicates(KEY_COLUMNS, keep="first").copy()


def direction_name(counter_trade: bool) -> str:
    return "counter" if counter_trade else "trend"


def symbol_components(symbol: str) -> set[str]:
    return {
        token.strip()
        for token in str(symbol).split("_")
        if token.strip()
    }


def shared_components(target: str, ref: str) -> list[str]:
    shared = symbol_components(target) & symbol_components(ref)
    return sorted(shared)


def joined(values) -> str:
    cleaned = sorted({str(value) for value in values if str(value)})
    return ",".join(cleaned)


def shape_mode(shapes: pd.Series) -> tuple[str, int, float]:
    valid = shapes[shapes.isin(EVENT_SHAPES)]
    if valid.empty:
        return "", 0, np.nan

    counts = valid.value_counts()
    max_count = int(counts.max())
    modes = sorted(counts[counts == max_count].index.tolist())
    mode = ",".join(modes)
    ratio = max_count / len(valid)
    return mode, max_count, ratio


def build_pair_summary(representatives: pd.DataFrame) -> pd.DataFrame:
    candidates = representatives[
        representatives["discovery_candidate"]
        & ~representatives["is_self_pair"]
    ].copy()
    candidates["direction"] = candidates["counter_trade"].map(direction_name)

    rows = []
    for (target, ref), group in candidates.groupby(
        ["target", "ref"],
        sort=False,
    ):
        direction_sets = (
            group.groupby("signal_type", sort=False)["direction"]
            .agg(lambda values: frozenset(values))
            .to_dict()
        )
        trend_only_types = {
            signal_type
            for signal_type, directions in direction_sets.items()
            if directions == {"trend"}
        }
        counter_only_types = {
            signal_type
            for signal_type, directions in direction_sets.items()
            if directions == {"counter"}
        }
        bidirectional_types = {
            signal_type
            for signal_type, directions in direction_sets.items()
            if directions == {"trend", "counter"}
        }

        candidate_types = set(direction_sets)
        trend_candidates = group[group["direction"] == "trend"]
        counter_candidates = group[group["direction"] == "counter"]

        if len(trend_only_types) > len(counter_only_types):
            consensus_direction = "trend"
            consensus_types = trend_only_types
        elif len(counter_only_types) > len(trend_only_types):
            consensus_direction = "counter"
            consensus_types = counter_only_types
        else:
            consensus_direction = "tie"
            consensus_types = set()

        consensus_group = group[
            group["signal_type"].isin(consensus_types)
            & (group["direction"] == consensus_direction)
        ]
        consensus_count = len(consensus_types)
        opposite_count = min(
            len(trend_only_types),
            len(counter_only_types),
        )
        candidate_count = len(candidate_types)
        exclusive_count = len(trend_only_types) + len(counter_only_types)
        direction_ratio = (
            consensus_count / candidate_count
            if candidate_count
            else np.nan
        )
        exclusive_ratio = (
            consensus_count / exclusive_count
            if exclusive_count
            else np.nan
        )

        state_group = consensus_group[
            consensus_group["signal_class"] == "state"
        ]
        event_group = consensus_group[
            consensus_group["signal_class"] == "event"
        ]

        mode, mode_count, mode_ratio = shape_mode(
            event_group["response_shape"]
        )

        component_list = shared_components(target, ref)
        row = {
            "target": target,
            "ref": ref,
            "has_shared_component": bool(component_list),
            "shared_components": ",".join(component_list),
            "candidate_signal_count": candidate_count,
            "trend_candidate_signal_count": int(
                trend_candidates["signal_type"].nunique()
            ),
            "counter_candidate_signal_count": int(
                counter_candidates["signal_type"].nunique()
            ),
            "trend_only_signal_count": len(trend_only_types),
            "counter_only_signal_count": len(counter_only_types),
            "bidirectional_signal_count": len(bidirectional_types),
            "consensus_direction": consensus_direction,
            "consensus_signal_count": consensus_count,
            "opposite_signal_count": opposite_count,
            "direction_consistency_ratio": direction_ratio,
            "exclusive_direction_consistency_ratio": exclusive_ratio,
            "trend_candidate_signal_types": joined(
                trend_candidates["signal_type"]
            ),
            "counter_candidate_signal_types": joined(
                counter_candidates["signal_type"]
            ),
            "trend_only_signal_types": joined(trend_only_types),
            "counter_only_signal_types": joined(counter_only_types),
            "bidirectional_signal_types": joined(bidirectional_types),
            "consensus_signal_types": joined(consensus_types),
            "consensus_state_signal_count": int(
                state_group["signal_type"].nunique()
            ),
            "consensus_event_signal_count": int(
                event_group["signal_type"].nunique()
            ),
            "consensus_state_signal_types": joined(state_group["signal_type"]),
            "consensus_event_signal_types": joined(event_group["signal_type"]),
            "has_state_and_event_confirmation": bool(
                not state_group.empty and not event_group.empty
            ),
            "consensus_median_discovery_t": (
                float(consensus_group["discovery_t_value"].median())
                if not consensus_group.empty
                else np.nan
            ),
            "consensus_max_discovery_t": (
                float(consensus_group["discovery_t_value"].max())
                if not consensus_group.empty
                else np.nan
            ),
            "event_shape_signal_count": int(len(event_group)),
            "event_shape_mode": mode,
            "event_shape_mode_count": mode_count,
            "event_shape_consistency_ratio": mode_ratio,
            "event_shapes": joined(event_group["response_shape"]),
        }

        for shape in EVENT_SHAPES:
            row[f"event_{shape}_count"] = int(
                (event_group["response_shape"] == shape).sum()
            )

        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    return result.sort_values(
        [
            "consensus_signal_count",
            "direction_consistency_ratio",
            "has_state_and_event_confirmation",
            "consensus_median_discovery_t",
            "target",
            "ref",
        ],
        ascending=[False, False, False, False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)

def build_details(
    representatives: pd.DataFrame,
    pair_summary: pd.DataFrame,
) -> pd.DataFrame:
    details = representatives[
        representatives["discovery_candidate"]
        & ~representatives["is_self_pair"]
    ].copy()
    details["direction"] = details["counter_trade"].map(direction_name)

    output_columns = [
        "target",
        "ref",
        "signal_type",
        "signal_class",
        "direction",
        "signal_direction_status",
        "discovery_hold",
        "discovery_average_pct",
        "discovery_t_value",
        "response_shape",
        "consensus_direction",
        "consensus_signal_count",
        "direction_consistency_ratio",
        "has_shared_component",
        "shared_components",
        "source_hold_response",
    ]
    if details.empty:
        return pd.DataFrame(columns=output_columns)

    pair_columns = [
        "target",
        "ref",
        "consensus_direction",
        "consensus_signal_count",
        "direction_consistency_ratio",
        "has_shared_component",
        "shared_components",
        "bidirectional_signal_types",
    ]
    details = details.merge(
        pair_summary[pair_columns],
        on=["target", "ref"],
        how="left",
        validate="many_to_one",
    )

    bidirectional_sets = details["bidirectional_signal_types"].fillna("").map(
        lambda value: set(filter(None, str(value).split(",")))
    )
    details["signal_direction_status"] = "opposite"
    is_bidirectional = [
        signal_type in signal_set
        for signal_type, signal_set in zip(
            details["signal_type"],
            bidirectional_sets,
        )
    ]
    details.loc[is_bidirectional, "signal_direction_status"] = "bidirectional"
    no_consensus = details["consensus_direction"] == "tie"
    details.loc[
        no_consensus & ~pd.Series(is_bidirectional, index=details.index),
        "signal_direction_status",
    ] = "no_consensus"
    matches = (
        (details["direction"] == details["consensus_direction"])
        & ~pd.Series(is_bidirectional, index=details.index)
    )
    details.loc[matches, "signal_direction_status"] = "consensus"

    details = details[output_columns]
    status_order = {
        "consensus": 0,
        "bidirectional": 1,
        "opposite": 2,
        "no_consensus": 3,
    }
    details["_status_order"] = details["signal_direction_status"].map(status_order)
    details = details.sort_values(
        [
            "consensus_signal_count",
            "target",
            "ref",
            "_status_order",
            "signal_class",
            "signal_type",
        ],
        ascending=[False, True, True, True, True, True],
        kind="mergesort",
    ).drop(columns="_status_order")
    return details.reset_index(drop=True)

def build_tasks(
    representatives: pd.DataFrame,
    pair_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Discovery候補の完全なStrategyTaskを保存する。"""
    tasks = representatives[
        representatives["discovery_candidate"]
        & ~representatives["is_self_pair"]
    ].copy()
    tasks["direction"] = tasks["counter_trade"].map(direction_name)

    output_columns = [
        "target",
        "ref",
        "signal_type",
        "counter_trade",
        "use_excess_return",
        "threshold_width",
        "hold_days",
        "start_days",
        "sma_period",
        "sma_period_relevant",
        "signal_class",
        "direction",
        "signal_direction_status",
        "response_shape",
        "discovery_trade_count",
        "discovery_average_pct",
        "discovery_t_value",
        "consensus_direction",
        "consensus_signal_count",
        "direction_consistency_ratio",
        "has_shared_component",
        "shared_components",
        "source_hold_response",
    ]
    if tasks.empty:
        return pd.DataFrame(columns=output_columns)

    pair_columns = [
        "target",
        "ref",
        "consensus_direction",
        "consensus_signal_count",
        "direction_consistency_ratio",
        "has_shared_component",
        "shared_components",
        "bidirectional_signal_types",
    ]
    tasks = tasks.merge(
        pair_summary[pair_columns],
        on=["target", "ref"],
        how="left",
        validate="many_to_one",
    )

    bidirectional_sets = tasks["bidirectional_signal_types"].fillna("").map(
        lambda value: set(filter(None, str(value).split(",")))
    )
    is_bidirectional = pd.Series(
        [
            signal_type in signal_set
            for signal_type, signal_set in zip(
                tasks["signal_type"],
                bidirectional_sets,
            )
        ],
        index=tasks.index,
    )

    tasks["signal_direction_status"] = "opposite"
    tasks.loc[is_bidirectional, "signal_direction_status"] = "bidirectional"
    no_consensus = tasks["consensus_direction"] == "tie"
    tasks.loc[
        no_consensus & ~is_bidirectional,
        "signal_direction_status",
    ] = "no_consensus"
    matches = (
        (tasks["direction"] == tasks["consensus_direction"])
        & ~is_bidirectional
    )
    tasks.loc[matches, "signal_direction_status"] = "consensus"

    # discovery_hold はISで観察対象として固定した実際の保有日数。
    # Developmentではこの値をStrategyTask.hold_daysとしてそのまま使う。
    tasks["hold_days"] = pd.to_numeric(
        tasks["discovery_hold"],
        errors="raise",
    ).astype("Int64")
    tasks["start_days"] = pd.to_numeric(
        tasks["start_days"],
        errors="raise",
    ).astype("Int64")
    tasks["sma_period_relevant"] = tasks["sma_period"].notna()
    tasks["sma_period"] = pd.to_numeric(
        tasks["task_sma_period"],
        errors="raise",
    ).astype("Int64")
    tasks["discovery_trade_count"] = pd.to_numeric(
        tasks["discovery_trade_count"],
        errors="coerce",
    ).astype("Int64")

    status_order = {
        "consensus": 0,
        "bidirectional": 1,
        "opposite": 2,
        "no_consensus": 3,
    }
    tasks["_status_order"] = tasks["signal_direction_status"].map(status_order)
    tasks = tasks.sort_values(
        [
            "consensus_signal_count",
            "target",
            "ref",
            "_status_order",
            "signal_class",
            "signal_type",
        ],
        ascending=[False, True, True, True, True, True],
        kind="mergesort",
    ).drop(columns="_status_order")
    return tasks[output_columns].reset_index(drop=True)


def build_summary(pair_summary: pd.DataFrame, details: pd.DataFrame) -> pd.DataFrame:
    if pair_summary.empty:
        return pd.DataFrame([
            {
                "pair_count_with_candidate": 0,
                "candidate_signal_rows": 0,
                "multi_signal_pair_count": 0,
                "same_direction_multi_signal_pair_count": 0,
                "unanimous_direction_multi_signal_pair_count": 0,
                "state_and_event_confirmation_pair_count": 0,
                "event_shape_multi_signal_pair_count": 0,
                "shared_component_pair_count": 0,
            }
        ])

    return pd.DataFrame([
        {
            "pair_count_with_candidate": len(pair_summary),
            "candidate_signal_rows": len(details),
            "multi_signal_pair_count": int(
                (pair_summary["candidate_signal_count"] >= 2).sum()
            ),
            "same_direction_multi_signal_pair_count": int(
                (pair_summary["consensus_signal_count"] >= 2).sum()
            ),
            "unanimous_direction_multi_signal_pair_count": int((
                (pair_summary["candidate_signal_count"] >= 2)
                & (pair_summary["direction_consistency_ratio"] == 1.0)
            ).sum()),
            "state_and_event_confirmation_pair_count": int(
                pair_summary["has_state_and_event_confirmation"].sum()
            ),
            "event_shape_multi_signal_pair_count": int(
                (pair_summary["event_shape_signal_count"] >= 2).sum()
            ),
            "shared_component_pair_count": int(
                pair_summary["has_shared_component"].sum()
            ),
        }
    ])


def run(
    hold_response_paths: list[Path],
    output_dir: Path,
):
    representatives = read_hold_responses(hold_response_paths)
    pair_summary = build_pair_summary(representatives)
    details = build_details(representatives, pair_summary)
    tasks = build_tasks(representatives, pair_summary)
    summary = build_summary(pair_summary, details)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    pair_summary.to_csv(
        output_dir / "signal_consensus_pairs.csv",
        **csv_options,
    )
    details.to_csv(
        output_dir / "signal_consensus_details.csv",
        **csv_options,
    )
    tasks.to_csv(
        output_dir / "signal_consensus_tasks.csv",
        **csv_options,
    )
    summary.to_csv(
        output_dir / "signal_consensus_summary.csv",
        **csv_options,
    )

    print("=== Signal Consensus ===")
    print(f"family representatives: {len(representatives)}")
    print(f"cross-market discovery rows: {len(details)}")
    print(f"frozen StrategyTask rows: {len(tasks)}")
    print(f"pairs with candidate: {len(pair_summary)}")
    if not pair_summary.empty:
        print(
            "same-direction multi-signal pairs: "
            f"{int((pair_summary['consensus_signal_count'] >= 2).sum())}"
        )
        print(
            "state + event confirmation pairs: "
            f"{int(pair_summary['has_state_and_event_confirmation'].sum())}"
        )
    print(f"output: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "hold_response_series.csvをTarget/Ref単位にまとめ、"
            "signal横断の方向一致・Event shape再現性を観察する。"
        )
    )
    parser.add_argument(
        "--hold-response",
        type=Path,
        nargs="+",
        required=True,
        help="1つ以上のhold_response_series.csv。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results") / "signal_consensus",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        hold_response_paths=args.hold_response,
        output_dir=args.output_dir,
    )
