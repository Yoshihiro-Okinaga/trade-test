import math
from typing import List, Optional
from dataclasses import dataclass, field


# --- コンフィグ ---
VALID_SIGNAL_TYPES = {"change", "sma", "bb", "macd", "rsi", "di", "stoch", "Test"}
VALID_TRADE_CODE_TYPES = {"all", "same", "not_same"}


class BackTestConfig:
    def __init__(self, config_data):
        self.ref_list: List[str] = config_data.get("ref_list", [])
        self.target_list: dict = config_data.get("target_list", {})
        self.signal_type_list: List[str] = config_data.get("signal_type_list", [])
        self.ref_lag_days_list: List[int] = config_data.get("ref_lag_days_list", [])
        self.hold_days_list: List[int] = config_data.get("hold_days_list", [])
        self.start_days_list: List[int] = config_data.get("start_days_list", [])
        self.sma_period_list: List[int] = config_data.get("sma_period_list", [])
        self.trade_code_type: str = config_data.get("trade_code_type", "all")
        self.min_trade_count: int = config_data.get("min_trade_count", 10)
        self.counter_trade: bool = config_data.get("counter_trade", False)
        self.calc_only_correlation: bool = config_data.get("calc_only_correlation", False)
        self.use_process_pool: bool = config_data.get("use_process_pool", True)
        # 指標ごとの売買判定の閾値（幅）。center は 0 固定で、
        # |signal| がこの width を超えたら売買シグナルとする。
        # 指標ごとに値のスケールが違うため、指標名 -> width の辞書で持つ。
        # 未指定の指標は default_threshold_width を使う（従来の RISE_PERCENT 相当）。
        self.threshold_width: dict = config_data.get("threshold_width", {})
        self.default_threshold_width: float = config_data.get("default_threshold_width", 1.0)
        # 指標ごとの中心値。rsi/stoch のように中心が 0 でない指標のために使う。
        # 未指定の指標は中心 0（bb, change, sma, macd, di など）。
        self.threshold_center: dict = config_data.get("threshold_center", {})
        # 重複補正: True の場合、あるポジションを保有している間は
        # 同方向の新規エントリーをしない（保有期間の重なりを排除する）。
        # long と short は独立に管理する（両建てあり）。
        # False なら従来通り、毎日シグナルが出るたびエントリーする。
        self.no_overlap: bool = config_data.get("no_overlap", False)

        self.validate()

    def validate(self):
        """設定値がバックテストで使用できる形式か確認する。"""
        if not isinstance(self.ref_list, list) or not self.ref_list or not all(
            isinstance(value, str) and value for value in self.ref_list
        ):
            raise ValueError("ref_listには1件以上の銘柄名を指定してください。")

        if not isinstance(self.target_list, dict) or not self.target_list:
            raise ValueError("target_listには1件以上の銘柄と売買コストを指定してください。")
        for name, cost in self.target_list.items():
            if not isinstance(name, str) or not name:
                raise ValueError("target_listの銘柄名は空でない文字列にしてください。")
            if not self._is_finite_number(cost) or cost < 0:
                raise ValueError(f"target_list.{name}の売買コストは0以上の数値にしてください。")

        if not isinstance(self.signal_type_list, list) or not self.signal_type_list:
            raise ValueError("signal_type_listには1件以上の指標を指定してください。")
        invalid_signal_types = [
            value for value in self.signal_type_list
            if value not in VALID_SIGNAL_TYPES
        ]
        if invalid_signal_types:
            raise ValueError(
                "未対応のsignal_typeがあります: " + ", ".join(map(str, invalid_signal_types))
            )

        positive_integer_lists = {
            "ref_lag_days_list": self.ref_lag_days_list,
            "hold_days_list": self.hold_days_list,
            "start_days_list": self.start_days_list,
            "sma_period_list": self.sma_period_list,
        }
        for name, values in positive_integer_lists.items():
            if not isinstance(values, list) or not values or not all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 1
                for value in values
            ):
                raise ValueError(f"{name}には1以上の整数を1件以上指定してください。")

        if self.trade_code_type not in VALID_TRADE_CODE_TYPES:
            valid_values = ", ".join(sorted(VALID_TRADE_CODE_TYPES))
            raise ValueError(f"trade_code_typeは次のいずれかにしてください: {valid_values}")

        if (
            not isinstance(self.min_trade_count, int)
            or isinstance(self.min_trade_count, bool)
            or self.min_trade_count < 1
        ):
            raise ValueError("min_trade_countは1以上の整数にしてください。")

        boolean_settings = {
            "counter_trade": self.counter_trade,
            "calc_only_correlation": self.calc_only_correlation,
            "use_process_pool": self.use_process_pool,
            "no_overlap": self.no_overlap,
        }
        for name, value in boolean_settings.items():
            if not isinstance(value, bool):
                raise ValueError(f"{name}はtrueまたはfalseにしてください。")

        if (
            not self._is_finite_number(self.default_threshold_width)
            or self.default_threshold_width < 0
        ):
            raise ValueError("default_threshold_widthは0以上の数値にしてください。")

        self._validate_signal_number_dict(
            "threshold_width", self.threshold_width, minimum=0
        )
        self._validate_signal_number_dict("threshold_center", self.threshold_center)

    @staticmethod
    def _is_finite_number(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )

    @classmethod
    def _validate_signal_number_dict(cls, name, values, minimum=None):
        if not isinstance(values, dict):
            raise ValueError(f"{name}は指標名と数値の辞書にしてください。")

        for signal_type, value in values.items():
            if signal_type not in VALID_SIGNAL_TYPES:
                raise ValueError(f"{name}に未対応の指標があります: {signal_type}")
            if not cls._is_finite_number(value):
                raise ValueError(f"{name}.{signal_type}は有限の数値にしてください。")
            if minimum is not None and value < minimum:
                raise ValueError(f"{name}.{signal_type}は{minimum}以上にしてください。")

    def width_of(self, signal_type: str) -> float:
        """指標に対応する閾値の幅を返す。未設定ならデフォルト。"""
        return self.threshold_width.get(signal_type, self.default_threshold_width)

    def center_of(self, signal_type: str) -> float:
        """指標に対応する中心値を返す。未設定なら 0。"""
        return self.threshold_center.get(signal_type, 0.0)

