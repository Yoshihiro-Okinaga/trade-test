from dataclasses import dataclass
from typing import TYPE_CHECKING

from backtest_config import SignalType

if TYPE_CHECKING:
    from backtest_config import BackTestConfig


@dataclass(frozen=True, order=True)
class StrategyTask:
    ref_name: str
    target_name: str
    signal_type: SignalType
    counter_trade: bool
    use_excess_return: bool
    threshold_width: float
    hold_days: int
    start_days: int
    sma_period: int

    def as_backtest_args(self) -> tuple:
        """既存の calc_trade_results に渡す引数を従来と同じ順序で返す。"""
        return (
            self.ref_name,
            self.target_name,
            self.signal_type,
            self.counter_trade,
            self.use_excess_return,
            self.threshold_width,
            self.hold_days,
            self.start_days,
            self.sma_period,
        )


def build_strategy_tasks(config: "BackTestConfig") -> list[StrategyTask]:
    """設定から実行する戦略パラメータの全組み合わせを作る。"""
    return [
        StrategyTask(
            ref_name=ref_name,
            target_name=target_name,
            signal_type=signal_type,
            counter_trade=counter_trade,
            use_excess_return=use_excess_return,
            threshold_width=threshold_width,
            hold_days=hold_days,
            start_days=start_days,
            sma_period=sma_period,
        )
        for ref_name, target_name in config.iter_ref_target()
        for signal_type in config.signal_type_list
        for counter_trade in config.counter_trade
        for use_excess_return in config.use_excess_return
        # 閾値は指標ごとにスケールが違うので、指標ごとの候補リストを展開する。
        for threshold_width in config.widths_of(signal_type)
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]
