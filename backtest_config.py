from typing import List, Optional
from dataclasses import dataclass, field


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
        self.counter_trade: List[bool] = config_data.get("counter_trade", [False])
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
        # 売買のフィルタ。指定するとその指標の値が filter_max 以下の日だけ
        # エントリーする。空文字ならフィルタなし（従来と同じ挙動）。
        self.filter_signal_type: str = config_data.get("filter_signal_type", "")
        self.filter_max: float = config_data.get("filter_max", 25.0)
        # 超過リターン評価: True の場合、各トレードの損益から
        # 「その銘柄を単に保有していた場合の平均的な変動（ドリフト）」を差し引く。
        # long からは追い風を、short からは逆風を取り除くので、
        # 市場全体の方向バイアスを除いた純粋な優位性を測れる。
        self.use_excess_return: List[bool] = config_data.get("use_excess_return", [False])
        # 期間別の成績を出すための区切り年。
        # [2001, 2006, 2011, 2016, 2021] と書くと
        # 2001-2005, 2006-2010, 2011-2015, 2016-2020, 2021以降 に分割して
        # それぞれの average_pct と trade_count を列として出力する。
        # 空リストなら期間別の集計をしない。
        self.period_years: List[int] = config_data.get("period_years", [])

    def width_of(self, signal_type: str) -> float:
        """指標に対応する閾値の幅を返す。未設定ならデフォルト。
        リストが設定されている場合は先頭の値を返す。"""
        value = self.threshold_width.get(signal_type, self.default_threshold_width)
        if isinstance(value, (list, tuple)):
            return value[0]
        return value

    def widths_of(self, signal_type: str) -> list:
        """指標に対応する閾値の候補を一覧で返す。
        config に数値を書けば1件、リストを書けばその全件を試せる。
        例: bb = [1.0, 1.5, 2.0] と書くと3通りを別々のタスクとして回す。"""
        value = self.threshold_width.get(signal_type, self.default_threshold_width)
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    def center_of(self, signal_type: str) -> float:
        """指標に対応する中心値を返す。未設定なら 0。"""
        return self.threshold_center.get(signal_type, 0.0)

