from typing import List, Optional
from dataclasses import dataclass, field


class BackTestConfig:
    def __init__(self, config_data):
        # 銘柄の定義（コスト・スワップ・グループ）は symbols に1箇所だけ書く。
        # 使う銘柄は symbol_groups（"fx" などのまとまり）か symbol_names
        # （個別指定）で選ぶ。両方書けば合算される。
        # target から外したいものだけ exclude_names に書く
        # （ref には含まれるが target にはならない）。
        self.symbols: dict = config_data.get("symbols", {})
        self.symbol_groups: List[str] = config_data.get("symbol_groups", [])
        self.symbol_names: List[str] = config_data.get("symbol_names", [])
        self.exclude_names: List[str] = config_data.get("exclude_names", [])

        # 存在しないグループ名を指定した場合、黙って空になると原因が分からないので
        # 先に知らせる（タイプミス対策）。
        defined_groups = {
            value.get("group") for value in self.symbols.values()
            if isinstance(value, dict) and value.get("group")
        }
        unknown_groups = [g for g in self.symbol_groups if g not in defined_groups]
        if unknown_groups:
            raise ValueError(
                "symbolsに存在しないグループです: " + ", ".join(unknown_groups)
                + "（定義済み: " + ", ".join(sorted(defined_groups)) + "）"
            )

        # グループ指定を銘柄名に展開する。symbols での定義順を保つ。
        wanted_groups = set(self.symbol_groups)
        selected: List[str] = [
            name for name, value in self.symbols.items()
            if isinstance(value, dict) and value.get("group") in wanted_groups
        ]
        # 個別指定を後ろに足す（グループで既に入っているものは重複させない）
        for name in self.symbol_names:
            if name not in selected:
                selected.append(name)

        if not selected:
            raise ValueError("symbol_groups か symbol_names で銘柄を指定してください。")

        # symbols に定義がない銘柄は、コスト0として黙って計算されてしまうため、
        # 起動時に気づけるようにする。
        undefined = [name for name in selected if name not in self.symbols]
        if undefined:
            raise ValueError("symbolsに定義がない銘柄があります: " + ", ".join(undefined))

        # ref は選ばれた全銘柄、target は除外を引いたもの。
        excluded = set(self.exclude_names)
        self.ref_list: List[str] = selected
        self.target_list: List[str] = [n for n in selected if n not in excluded]
        if not self.target_list:
            raise ValueError("exclude_namesで全銘柄が除外されています。")
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

    def cost_of(self, target_name: str) -> float:
        """銘柄の売買コスト（値幅）を返す。
        symbols には数値でも { cost = ..., swap = ... } の辞書でも書ける。
        未設定なら 0。"""
        value = self.symbols.get(target_name)
        if isinstance(value, dict):
            value = value.get("cost", 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def swap_of(self, target_name: str) -> float:
        """銘柄の日次スワップ率（％／日）を返す。
        ロング保有時に受け取る率で、プラスならロングで受け取り。
        ショートは符号を反転させた率になる（売買が対称と仮定）。
        未設定なら 0。"""
        value = self.symbols.get(target_name)
        if isinstance(value, dict):
            try:
                return float(value.get("swap", 0.0))
            except (TypeError, ValueError):
                return 0.0
        return 0.0

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

