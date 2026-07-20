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
