from dataclasses import dataclass
from enum import StrEnum


class WalkForwardMode(StrEnum):
    ANCHORED = "anchored"
    ROLLING = "rolling"


class SelectionMetric(StrEnum):
    T_VALUE = "t_value"
    YEAR_T_VALUE = "year_t_value"
    LOWER_CONFIDENCE_BOUND = "lower_confidence_bound"
    AVERAGE_PCT = "average_pct"
    TOTAL_PCT = "total_pct"
    WORST_YEAR_PCT = "worst_year_pct"
    POSITIVE_YEAR_RATIO = "positive_year_ratio"
    HALF_SPLIT_MIN = "half_split_min"


class SelectionScope(StrEnum):
    TARGET = "target"
    GLOBAL = "global"


def _parse_enum(enum_type, value, setting_name):
    """設定値を Enum に変換し、不正値なら候補を含むエラーにする。"""
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(
            f"{setting_name} は次のいずれかを指定してください: {allowed}。"
            f"指定値: {value!r}"
        ) from exc


@dataclass
class WalkForwardConfig:
    train_years: int
    test_years: int
    step_years: int
    mode: WalkForwardMode
    select_metric: SelectionMetric
    select_per: SelectionScope
    select_top_k: int
    min_is_trades: int
    min_is_t: float
    max_open_positions: int

    @classmethod
    def from_config_data(cls, config_data: dict) -> "WalkForwardConfig":
        """config.toml の [walkforward] セクションを読み込む。"""
        wf = config_data.get("walkforward", {})
        test_years = int(wf.get("test_years", 2))

        return cls(
            train_years=int(wf.get("train_years", 8)),
            test_years=test_years,
            # 既定は検証期間ぶんスライド＝未知期間を重ねない
            step_years=int(wf.get("step_years", test_years)),
            mode=_parse_enum(
                WalkForwardMode,
                wf.get("mode", WalkForwardMode.ANCHORED),
                "walkforward.mode",
            ),
            select_metric=_parse_enum(
                SelectionMetric,
                wf.get("select_metric", SelectionMetric.T_VALUE),
                "walkforward.select_metric",
            ),
            select_per=_parse_enum(
                SelectionScope,
                wf.get("select_per", SelectionScope.TARGET),
                "walkforward.select_per",
            ),
            select_top_k=int(wf.get("select_top_k", 1)),
            min_is_trades=int(wf.get("min_is_trades", 30)),
            # 品質ゲート: 各銘柄の最良候補でも学習期間の t値がこの値未満なら、
            # その銘柄はその期間は見送る（張らない）。0.0 でゲート無効＝従来どおり。
            min_is_t=float(wf.get("min_is_t", 0.0)),
            # ポートフォリオ全体の同時建玉数。0 は無制限。
            max_open_positions=int(wf.get("max_open_positions", 0)),
        )
