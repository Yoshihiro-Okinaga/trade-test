import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROUND_DIGITS = 9
DEFAULT_MIN_TRADES = 150
DEFAULT_DISCOVERY_HOLD = 1
DEFAULT_EVENT_DISCOVERY_HOLDS = [1, 2, 3, 4, 5]
DEFAULT_DISCOVERY_MIN_T = 2.0
DEFAULT_RESPONSE_MATERIAL_RATIO = 0.25
T80_RATIO = 0.80

RESPONSE_SHAPES = [
    "fast_decay",
    "short_plateau",
    "persistent",
    "late_extension",
    "mixed",
]

# Eventは「発生した瞬間」に意味があるシグナル。
# Stateは「現在の市場状態」を表すシグナル。
# この分類は選抜条件ではなく、hold responseを解釈するためのラベル。
EVENT_SIGNALS = {"macd", "streak", "breakout"}
STATE_SIGNALS = {"change", "sma", "bb", "rsi", "di", "stoch"}

# 現行実装では以下のシグナルはsma_periodに依存しない。
# strategy_screening側ではsma_periodごとに同一結果が生成され得るので、
# hold response分析では1系列へ正規化する。
PERIOD_INDEPENDENT_SIGNALS = EVENT_SIGNALS

SERIES_COLUMNS = [
    "target",
    "ref",
    "signal_type",
    "counter_trade",
    "use_excess_return",
    "threshold_width",
    "start_days",
    "analysis_sma_period",
]

FAMILY_COLUMNS = [
    "target",
    "ref",
    "signal_type",
    "counter_trade",
    "use_excess_return",
]

REQUIRED_COLUMNS = [
    "target",
    "ref",
    "signal_type",
    "counter_trade",
    "use_excess_return",
    "threshold_width",
    "hold_days",
    "start_days",
    "sma_period",
    "trade_count",
    "average_pct",
    "t_value",
]

METRIC_COLUMNS = ["trade_count", "average_pct", "t_value"]


def signal_class_of(signal_type: str) -> str:
    if signal_type in EVENT_SIGNALS:
        return "event"
    if signal_type in STATE_SIGNALS:
        return "state"
    return "other"


def read_rankings(paths: list[Path]) -> pd.DataFrame:
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
            raise ValueError(
                f"{path} に必要な列がありません: {missing}"
            )
        frame["source_ranking"] = str(path)
        frames.append(frame)

    if not frames:
        raise ValueError("ranking CSVを1つ以上指定してください。")

    ranking = pd.concat(frames, ignore_index=True)
    normalize_ranking(ranking)
    return ranking


def normalize_ranking(ranking: pd.DataFrame):
    ranking["signal_type"] = ranking["signal_type"].astype(str)

    numeric_columns = [
        "threshold_width",
        "hold_days",
        "start_days",
        "sma_period",
        "trade_count",
        "average_pct",
        "t_value",
    ]
    for column in numeric_columns:
        ranking[column] = pd.to_numeric(
            ranking[column],
            errors="coerce",
        )

    required_numeric = [
        "threshold_width",
        "hold_days",
        "start_days",
        "sma_period",
        "trade_count",
        "average_pct",
        "t_value",
    ]
    if ranking[required_numeric].isna().any().any():
        bad_columns = [
            column
            for column in required_numeric
            if ranking[column].isna().any()
        ]
        raise ValueError(
            "数値列に欠損または変換不能な値があります: "
            + ", ".join(bad_columns)
        )

    ranking["hold_days"] = ranking["hold_days"].astype(int)
    ranking["start_days"] = ranking["start_days"].astype(int)
    ranking["sma_period"] = ranking["sma_period"].astype(int)
    ranking["trade_count"] = ranking["trade_count"].astype(int)

    # analysis_sma_periodは分析系列をまとめるための値。
    # task_sma_periodは後で完全なStrategyTaskを再現するため、
    # 元のsma_periodを別に保持する。
    ranking["task_sma_period"] = ranking["sma_period"]
    ranking["analysis_sma_period"] = ranking["sma_period"]
    independent = ranking["signal_type"].isin(
        PERIOD_INDEPENDENT_SIGNALS
    )
    ranking.loc[independent, "analysis_sma_period"] = -1


def validate_and_deduplicate(ranking: pd.DataFrame) -> pd.DataFrame:
    task_columns = SERIES_COLUMNS + ["hold_days"]
    duplicated = ranking.duplicated(task_columns, keep=False)
    if not duplicated.any():
        return ranking

    duplicate_rows = ranking.loc[duplicated]
    spread = duplicate_rows.groupby(
        task_columns,
        dropna=False,
        sort=False,
    )[METRIC_COLUMNS].agg(lambda values: values.max() - values.min())

    if (
        (spread["trade_count"] != 0)
        | (spread["average_pct"].abs() > 1e-12)
        | (spread["t_value"].abs() > 1e-12)
    ).any():
        raise ValueError(
            "sma_period非依存シグナル等の重複行で成績が一致しません。"
            "同じ分析系列へ安全に統合できません。"
        )

    # MACD / streak / breakoutなど、sma_periodに依存しないシグナルの
    # 重複タスクをここで1件にする。完全なStrategyTaskを後で再現できるよう、
    # 同一分析系列では元sma_periodの最小値を代表値として決定的に残す。
    ranking = ranking.sort_values(
        task_columns + ["task_sma_period"],
        ascending=True,
        kind="mergesort",
    )
    return ranking.drop_duplicates(task_columns, keep="first").copy()


def pivot_metric(
    ranking: pd.DataFrame,
    metric: str,
    holds: list[int],
) -> pd.DataFrame:
    pivot = ranking.pivot(
        index=SERIES_COLUMNS,
        columns="hold_days",
        values=metric,
    )
    return pivot.reindex(columns=holds)


def first_hold_reaching_ratio(
    averages: np.ndarray,
    holds: np.ndarray,
    peak_average: np.ndarray,
    ratio: float,
) -> np.ndarray:
    threshold = peak_average * ratio
    valid_peak = peak_average > 0
    reached = averages >= threshold[:, None]
    reached &= valid_peak[:, None]

    has_match = reached.any(axis=1)
    first_index = reached.argmax(axis=1)
    result = np.full(len(averages), np.nan)
    result[has_match] = holds[first_index[has_match]]
    return result


def safe_ratio(numerator: np.ndarray, denominator: np.ndarray):
    result = np.full(len(numerator), np.nan)
    valid = np.isfinite(denominator) & (denominator != 0)
    result[valid] = numerator[valid] / denominator[valid]
    return result


def add_interval_metric(
    result: pd.DataFrame,
    average_pivot: pd.DataFrame,
    start_hold: int,
    end_hold: int,
):
    if start_hold not in average_pivot or end_hold not in average_pivot:
        return

    gain = (
        average_pivot[end_hold].to_numpy()
        - average_pivot[start_hold].to_numpy()
    )
    result[f"gain_pct_{start_hold}_{end_hold}"] = gain
    result[f"marginal_pct_per_day_{start_hold}_{end_hold}"] = (
        gain / (end_hold - start_hold)
    )


def add_event_response_shape(
    result: pd.DataFrame,
    average_pivot: pd.DataFrame,
    event_discovery_holds: list[int],
    material_ratio: float,
):
    """Event系列のhold responseへ観察用shapeラベルを付ける。

    1～5日などEvent discovery窓の最大average_pctを短期ピークとし、
    10 / 20 / 30日の平均損益がそこからどの程度残る・伸びるかを見る。
    ラベルはPASS/FAILではなく、response curveを読みやすくするためのもの。
    """
    if not 0 < material_ratio < 1:
        raise ValueError(
            "response material ratioは0より大きく1未満にしてください。"
        )

    event_mask = result["signal_class"].to_numpy() == "event"
    result["response_shape"] = "state_not_classified"
    result["response_shape_reason"] = "state_signal"
    result["response_material_ratio"] = material_ratio
    result["event_early_peak_hold"] = np.nan
    result["event_early_peak_average_pct"] = np.nan

    for hold in [10, 20, 30]:
        result[f"event_retention_h{hold}"] = np.nan

    if not event_mask.any():
        return

    required_holds = [10, 20, 30]
    missing = [
        hold for hold in required_holds
        if hold not in average_pivot.columns
    ]
    if missing:
        result.loc[event_mask, "response_shape"] = "insufficient_holds"
        result.loc[event_mask, "response_shape_reason"] = (
            "missing_late_holds:" + ",".join(str(value) for value in missing)
        )
        return

    early_holds = [
        hold for hold in event_discovery_holds
        if hold in average_pivot.columns
    ]
    if not early_holds:
        result.loc[event_mask, "response_shape"] = "insufficient_holds"
        result.loc[event_mask, "response_shape_reason"] = (
            "missing_event_discovery_holds"
        )
        return

    early_values = average_pivot[early_holds].to_numpy(dtype=float)
    valid_early = np.isfinite(early_values).any(axis=1)
    comparable_early = np.where(
        np.isfinite(early_values),
        early_values,
        -np.inf,
    )
    early_index = comparable_early.argmax(axis=1)
    rows = np.arange(len(result))
    early_peak = early_values[rows, early_index].astype(float)
    early_peak_hold = np.asarray(early_holds, dtype=float)[early_index]
    early_peak[~valid_early] = np.nan
    early_peak_hold[~valid_early] = np.nan

    result.loc[event_mask, "event_early_peak_hold"] = early_peak_hold[event_mask]
    result.loc[event_mask, "event_early_peak_average_pct"] = early_peak[event_mask]

    retention = {}
    for hold in required_holds:
        later = average_pivot[hold].to_numpy(dtype=float)
        ratio = safe_ratio(later, early_peak)
        retention[hold] = ratio
        result.loc[event_mask, f"event_retention_h{hold}"] = ratio[event_mask]

    low = 1.0 - material_ratio
    high = 1.0 + material_ratio

    for index in np.flatnonzero(event_mask):
        peak = early_peak[index]
        late = [retention[hold][index] for hold in required_holds]

        if not np.isfinite(peak):
            shape = "insufficient_holds"
            reason = "early_window_has_no_valid_average"
        elif peak <= 0:
            shape = "mixed"
            reason = "early_peak_average_not_positive"
        elif not np.isfinite(late).all():
            shape = "insufficient_holds"
            reason = "late_hold_average_missing"
        else:
            below = sum(value < low for value in late)
            later_max = max(late)
            retention_10, retention_20, retention_30 = late

            if (
                below >= 2
                and retention_30 < low
                and later_max <= high
            ):
                shape = "fast_decay"
                reason = "late_response_materially_below_early_peak"
            elif later_max > high:
                if retention_10 > high:
                    shape = "persistent"
                    reason = "response_extends_materially_by_hold10"
                else:
                    shape = "late_extension"
                    reason = "response_reextends_after_hold10"
            elif sum(value >= low for value in late) >= 2:
                shape = "short_plateau"
                reason = "late_response_stays_near_early_peak"
            else:
                shape = "mixed"
                reason = "response_does_not_match_simple_shape"

        result.at[index, "response_shape"] = shape
        result.at[index, "response_shape_reason"] = reason


def build_series_metrics(
    ranking: pd.DataFrame,
    discovery_hold: int,
    event_discovery_holds: list[int],
    min_trades: int,
    discovery_min_t: float,
    response_material_ratio: float,
) -> pd.DataFrame:
    holds = sorted(int(value) for value in ranking["hold_days"].unique())

    signal_types = set(ranking["signal_type"].unique())
    has_event = bool(signal_types & EVENT_SIGNALS)
    has_non_event = bool(signal_types - EVENT_SIGNALS)

    if has_non_event and discovery_hold not in holds:
        raise ValueError(
            f"State discovery hold={discovery_hold} がrankingにありません。"
            f"存在するhold: {holds}"
        )

    event_holds = sorted(dict.fromkeys(event_discovery_holds))
    if not event_holds:
        raise ValueError("Event discovery holdを1つ以上指定してください。")

    if has_event:
        missing_event_holds = [
            hold for hold in event_holds if hold not in holds
        ]
        if missing_event_holds:
            raise ValueError(
                "Event discovery holdがrankingにありません: "
                f"{missing_event_holds}。存在するhold: {holds}"
            )

    average_pivot = pivot_metric(ranking, "average_pct", holds)
    t_pivot = pivot_metric(ranking, "t_value", holds)
    trade_pivot = pivot_metric(ranking, "trade_count", holds)

    result = average_pivot.index.to_frame(index=False)
    average_values = average_pivot.to_numpy(dtype=float)
    hold_values = np.asarray(holds, dtype=float)

    valid_counts = np.isfinite(average_values).sum(axis=1)
    peak_index = np.nanargmax(average_values, axis=1)
    row_index = np.arange(len(result))
    peak_average = average_values[row_index, peak_index]
    peak_hold = hold_values[peak_index]

    result["signal_class"] = result["signal_type"].map(
        signal_class_of
    )
    result["is_self_pair"] = result["target"] == result["ref"]
    result["hold_count"] = valid_counts
    result["peak_hold"] = peak_hold
    result["peak_average_pct"] = peak_average
    result["t80_hold"] = first_hold_reaching_ratio(
        average_values,
        hold_values,
        peak_average,
        T80_RATIO,
    )
    result["positive_hold_ratio"] = (
        (average_values > 0).sum(axis=1) / valid_counts
    )

    first_average = average_values[:, 0]
    last_average = average_values[:, -1]
    result["first_hold"] = holds[0]
    result["last_hold"] = holds[-1]
    result["first_average_pct"] = first_average
    result["last_average_pct"] = last_average
    result["end_retention_ratio"] = safe_ratio(
        last_average,
        peak_average,
    )

    left_average = np.full(len(result), np.nan)
    right_average = np.full(len(result), np.nan)
    has_left = peak_index > 0
    has_right = peak_index < len(holds) - 1
    left_average[has_left] = average_values[
        row_index[has_left], peak_index[has_left] - 1
    ]
    right_average[has_right] = average_values[
        row_index[has_right], peak_index[has_right] + 1
    ]
    result["peak_left_average_pct"] = left_average
    result["peak_right_average_pct"] = right_average
    result["peak_left_ratio"] = safe_ratio(
        left_average,
        peak_average,
    )
    result["peak_right_ratio"] = safe_ratio(
        right_average,
        peak_average,
    )

    # Stateはhold=1など固定anchorでDiscoveryを見る。
    # Eventは発火後すぐにedgeが立ち上がるとは限らないため、
    # 1～5日などの短期窓の中で最も強い点を観察用代表値にする。
    # これはfinalなhold選抜ではなく、短命なEventをhold=1だけで
    # 見落とさないためのDiscovery目印。
    discovery_t = np.full(len(result), np.nan)
    discovery_average = np.full(len(result), np.nan)
    discovery_trades = np.full(len(result), np.nan)
    discovery_holds = np.full(len(result), np.nan)
    discovery_eligible = np.zeros(len(result), dtype=bool)
    discovery_pass = np.zeros(len(result), dtype=bool)
    discovery_mode = np.full(len(result), "state_anchor", dtype=object)
    discovery_hold_spec = np.full(
        len(result),
        str(discovery_hold),
        dtype=object,
    )

    event_mask = result["signal_class"].to_numpy() == "event"
    non_event_mask = ~event_mask

    if non_event_mask.any():
        state_t = t_pivot[discovery_hold].to_numpy(dtype=float)
        state_average = average_pivot[discovery_hold].to_numpy(dtype=float)
        state_trades = trade_pivot[discovery_hold].to_numpy(dtype=float)

        discovery_t[non_event_mask] = state_t[non_event_mask]
        discovery_average[non_event_mask] = state_average[non_event_mask]
        discovery_trades[non_event_mask] = state_trades[non_event_mask]
        discovery_holds[non_event_mask] = discovery_hold
        discovery_eligible[non_event_mask] = (
            state_trades[non_event_mask] >= min_trades
        )
        discovery_pass[non_event_mask] = (
            discovery_eligible[non_event_mask]
            & (state_t[non_event_mask] >= discovery_min_t)
        )

    if event_mask.any():
        event_t = t_pivot[event_holds].to_numpy(dtype=float)
        event_average = average_pivot[event_holds].to_numpy(dtype=float)
        event_trades = trade_pivot[event_holds].to_numpy(dtype=float)

        # trade_count条件を満たす短期holdだけをDiscovery比較対象にする。
        # 同じ系列で複数holdが条件を満たす場合は最大tを観察用代表値とし、
        # 同値なら短いholdを採る。これは最終holdの選抜ではない。
        event_eligible_matrix = event_trades >= min_trades
        comparable_t = np.where(
            event_eligible_matrix & np.isfinite(event_t),
            event_t,
            -np.inf,
        )
        event_best_index = comparable_t.argmax(axis=1)
        event_rows = np.arange(len(result))
        event_has_eligible = event_eligible_matrix.any(axis=1)

        event_best_t = event_t[event_rows, event_best_index]
        event_best_average = event_average[event_rows, event_best_index]
        event_best_trades = event_trades[event_rows, event_best_index]
        event_best_hold = np.asarray(event_holds)[event_best_index]

        # eligible holdが無い系列はDiscovery代表値を欠損にする。
        event_best_t = event_best_t.astype(float)
        event_best_average = event_best_average.astype(float)
        event_best_trades = event_best_trades.astype(float)
        event_best_hold = event_best_hold.astype(float)
        event_best_t[~event_has_eligible] = np.nan
        event_best_average[~event_has_eligible] = np.nan
        event_best_trades[~event_has_eligible] = np.nan
        event_best_hold[~event_has_eligible] = np.nan

        discovery_t[event_mask] = event_best_t[event_mask]
        discovery_average[event_mask] = event_best_average[event_mask]
        discovery_trades[event_mask] = event_best_trades[event_mask]
        discovery_holds[event_mask] = event_best_hold[event_mask]
        discovery_eligible[event_mask] = event_has_eligible[event_mask]
        discovery_pass[event_mask] = (
            event_has_eligible[event_mask]
            & (event_best_t[event_mask] >= discovery_min_t)
        )
        discovery_mode[event_mask] = "event_short_window"
        event_spec = ",".join(str(value) for value in event_holds)
        discovery_hold_spec[event_mask] = event_spec

    result["discovery_mode"] = discovery_mode
    result["discovery_hold_spec"] = discovery_hold_spec
    result["discovery_hold"] = discovery_holds
    result["discovery_trade_count"] = discovery_trades
    result["discovery_average_pct"] = discovery_average
    result["discovery_t_value"] = discovery_t
    result["discovery_eligible"] = discovery_eligible
    result["discovery_pass"] = discovery_pass

    add_interval_metric(result, average_pivot, 1, 5)
    add_interval_metric(result, average_pivot, 5, 10)
    add_interval_metric(result, average_pivot, 10, 20)
    add_interval_metric(result, average_pivot, 20, 30)

    add_event_response_shape(
        result=result,
        average_pivot=average_pivot,
        event_discovery_holds=event_holds,
        material_ratio=response_material_ratio,
    )

    # holdごとの値も1行で確認できるように残す。
    for hold in holds:
        result[f"average_pct_h{hold}"] = average_pivot[hold].to_numpy()
        result[f"t_value_h{hold}"] = t_pivot[hold].to_numpy()
        result[f"trade_count_h{hold}"] = trade_pivot[hold].to_numpy()

    task_sma_lookup = (
        ranking[
            SERIES_COLUMNS + ["task_sma_period"]
        ]
        .drop_duplicates(SERIES_COLUMNS, keep="first")
        .set_index(SERIES_COLUMNS)["task_sma_period"]
        .reindex(average_pivot.index)
    )
    result["task_sma_period"] = task_sma_lookup.to_numpy()

    # sma_periodは分析上の意味を表す。非依存signalでは空欄のままにし、
    # 実行用の完全Task値はtask_sma_periodへ分離して保存する。
    result["sma_period"] = result["analysis_sma_period"].replace(
        {-1: np.nan}
    )
    result = result.drop(columns=["analysis_sma_period"])

    return mark_family_representatives(result)


def mark_family_representatives(result: pd.DataFrame) -> pd.DataFrame:
    # 指標ごとのparameter数の違いでsummaryが偏らないよう、
    # Target/Ref/signal/directionごとにdiscovery tが最大の1系列だけを
    # summary用代表とする。最終strategy選抜ではない。
    sort_columns = FAMILY_COLUMNS + [
        "discovery_eligible",
        "discovery_t_value",
        "threshold_width",
        "sma_period",
    ]
    ascending = (
        [True] * len(FAMILY_COLUMNS)
        + [False, False, True, True]
    )

    sorted_result = result.sort_values(
        sort_columns,
        ascending=ascending,
        kind="mergesort",
        na_position="first",
    )
    representative_index = (
        sorted_result
        .groupby(FAMILY_COLUMNS, sort=False, dropna=False)
        .head(1)
        .index
    )

    result["is_family_representative"] = False
    result.loc[representative_index, "is_family_representative"] = True
    result["discovery_candidate"] = (
        result["is_family_representative"]
        & result["discovery_pass"]
        & ~result["is_self_pair"]
    )
    return result


def build_summary(series: pd.DataFrame) -> pd.DataFrame:
    representatives = series[
        series["is_family_representative"]
        & ~series["is_self_pair"]
    ].copy()

    rows = []
    for (signal_class, signal_type), frame in representatives.groupby(
        ["signal_class", "signal_type"],
        sort=True,
    ):
        candidates = frame[frame["discovery_pass"]]
        discovery_mode = str(frame["discovery_mode"].iloc[0])
        discovery_hold_spec = str(frame["discovery_hold_spec"].iloc[0])

        row = {
            "signal_class": signal_class,
            "signal_type": signal_type,
            "discovery_mode": discovery_mode,
            "discovery_hold_spec": discovery_hold_spec,
            "family_count": len(frame),
            "discovery_candidate_count": len(candidates),
        }

        if len(candidates):
            row.update({
                "median_peak_hold": candidates["peak_hold"].median(),
                "median_t80_hold": candidates["t80_hold"].median(),
                "peak_hold_le_5_ratio": (
                    candidates["peak_hold"] <= 5
                ).mean(),
                "peak_hold_le_10_ratio": (
                    candidates["peak_hold"] <= 10
                ).mean(),
                "t80_hold_le_5_ratio": (
                    candidates["t80_hold"] <= 5
                ).mean(),
                "t80_hold_le_10_ratio": (
                    candidates["t80_hold"] <= 10
                ).mean(),
                "median_end_retention_ratio": (
                    candidates["end_retention_ratio"].median()
                ),
                "median_positive_hold_ratio": (
                    candidates["positive_hold_ratio"].median()
                ),
            })
            for column in [
                "gain_pct_1_5",
                "gain_pct_5_10",
                "gain_pct_10_20",
                "gain_pct_20_30",
                "marginal_pct_per_day_1_5",
                "marginal_pct_per_day_5_10",
                "marginal_pct_per_day_10_20",
                "marginal_pct_per_day_20_30",
            ]:
                if column in candidates.columns:
                    row[f"median_{column}"] = candidates[column].median()

            if signal_class == "event":
                for shape in RESPONSE_SHAPES:
                    count = int((candidates["response_shape"] == shape).sum())
                    row[f"response_shape_{shape}_count"] = count
                    row[f"response_shape_{shape}_ratio"] = count / len(candidates)

        rows.append(row)

    return pd.DataFrame(rows)


def run(
    ranking_paths: list[Path],
    output_dir: Path,
    min_trades: int,
    discovery_hold: int,
    event_discovery_holds: list[int],
    discovery_min_t: float,
    response_material_ratio: float,
):
    ranking = read_rankings(ranking_paths)
    input_rows = len(ranking)
    ranking = validate_and_deduplicate(ranking)
    deduplicated_rows = len(ranking)

    series = build_series_metrics(
        ranking=ranking,
        discovery_hold=discovery_hold,
        event_discovery_holds=event_discovery_holds,
        min_trades=min_trades,
        discovery_min_t=discovery_min_t,
        response_material_ratio=response_material_ratio,
    )
    summary = build_summary(series)

    series = series.sort_values(
        [
            "discovery_candidate",
            "discovery_t_value",
            "target",
            "ref",
            "signal_type",
            "counter_trade",
            "threshold_width",
            "sma_period",
        ],
        ascending=[False, False, True, True, True, True, True, True],
        kind="mergesort",
        na_position="first",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )
    series.to_csv(
        output_dir / "hold_response_series.csv",
        **csv_options,
    )
    summary.to_csv(
        output_dir / "hold_response_summary.csv",
        **csv_options,
    )

    print("=== Hold Response ===")
    print(f"input rows: {input_rows}")
    print(f"deduplicated rows: {deduplicated_rows}")
    print(f"series: {len(series)}")
    print(f"State discovery hold: {discovery_hold}")
    print(
        "Event discovery holds: "
        + ", ".join(str(value) for value in event_discovery_holds)
    )
    print(
        "discovery candidates: "
        f"{int(series['discovery_candidate'].sum())}"
    )
    print(
        "Event response material ratio: "
        f"{response_material_ratio:.3f}"
    )
    print(f"output: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "IS rankingのhold_days別成績から、signalの時間応答を整理する。"
            "Event/State分類は解釈用で、PASS/FAIL gateではない。"
        )
    )
    parser.add_argument(
        "--ranking",
        type=Path,
        nargs="+",
        required=True,
        help="1つ以上のtrade_ranking_full.csv。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results") / "hold_response",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=DEFAULT_MIN_TRADES,
    )
    parser.add_argument(
        "--discovery-hold",
        type=int,
        default=DEFAULT_DISCOVERY_HOLD,
        help="State/other signalのDiscovery anchor hold。",
    )
    parser.add_argument(
        "--event-discovery-holds",
        type=int,
        nargs="+",
        default=DEFAULT_EVENT_DISCOVERY_HOLDS,
        help=(
            "Event signalの短期Discovery窓。"
            "既定値: 1 2 3 4 5"
        ),
    )
    parser.add_argument(
        "--discovery-min-t",
        type=float,
        default=DEFAULT_DISCOVERY_MIN_T,
    )
    parser.add_argument(
        "--response-material-ratio",
        type=float,
        default=DEFAULT_RESPONSE_MATERIAL_RATIO,
        help=(
            "Event response shapeで短期ピークとの差を"
            "意味のある変化とみなす相対幅。既定値: 0.25。"
            "選抜gateではない。"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        ranking_paths=args.ranking,
        output_dir=args.output_dir,
        min_trades=args.min_trades,
        discovery_hold=args.discovery_hold,
        event_discovery_holds=args.event_discovery_holds,
        discovery_min_t=args.discovery_min_t,
        response_material_ratio=args.response_material_ratio,
    )
