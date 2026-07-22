from typing import List, Optional
from dataclasses import dataclass, field


# --- コンフィグ ---
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

    def width_of(self, signal_type: str) -> float:
        """指標に対応する閾値の幅を返す。未設定ならデフォルト。"""
        return self.threshold_width.get(signal_type, self.default_threshold_width)

    def center_of(self, signal_type: str) -> float:
        """指標に対応する中心値を返す。未設定なら 0。"""
        return self.threshold_center.get(signal_type, 0.0)

