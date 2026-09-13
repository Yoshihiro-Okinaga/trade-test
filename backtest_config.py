from typing import List, Optional
from dataclasses import dataclass, field
from enum import StrEnum


# === 設定 ===
class TradeCodeType(StrEnum):
    SAME = "same"
    NOT_SAME = "not_same"
    ALL = "all"


class SignalType(StrEnum):
    #sma_periods使用
    CHANGE = "change"
    SMA = "sma"
    BB = "bb"
    RSI = "rsi"
    DI = "di"
    #ADX = "adx"
    STOCH = "stoch"
    #sma_periods不使用
    MACD = "macd"
    STREAK = "streak"
    BREAKOUT = "breakout"



class BackTestConfig:
    def __init__(self, config_data):
        # 銘柄の定義（コスト・スワップ・グループ）は symbols に1箇所だけ書く。
        # ref（シグナル源）と target（売買対象）は、それぞれ独立した
        # symbol_groups / symbol_names で選ぶ。
        # target から外したいものだけ target_exclude_names に書く。
        self.symbols: dict = config_data.get("symbols", {})
        self.ref_symbol_groups: List[str] = config_data.get(
            "ref_symbol_groups", []
        )
        self.ref_symbol_names: List[str] = config_data.get(
            "ref_symbol_names", []
        )
        self.target_symbol_groups: List[str] = config_data.get(
            "target_symbol_groups", []
        )
        self.target_symbol_names: List[str] = config_data.get(
            "target_symbol_names", []
        )
        self.target_exclude_names: List[str] = config_data.get(
            "target_exclude_names", []
        )

        # 存在しないグループ名を指定した場合、黙って空になると原因が分からないので
        # 先に知らせる（タイプミス対策）。
        defined_groups = {
            value.get("group") for value in self.symbols.values()
            if isinstance(value, dict) and value.get("group")
        }
        self._validate_symbol_groups(
            self.ref_symbol_groups,
            "ref_symbol_groups",
            defined_groups,
        )
        self._validate_symbol_groups(
            self.target_symbol_groups,
            "target_symbol_groups",
            defined_groups,
        )

        # --- ペア名指し（検証・運用用）を最優先で解釈する ------------------
        # symbol_pairs があれば「そのペアだけ」を回す（総当たりしない）。
        # 各要素は { target = "...", ref = "..." } のテーブル形式を推奨
        # （順序の曖昧さを排除）。[target, ref] の2要素配列も許容する。
        # 空/未指定なら ref_list × target_list の総当たり。
        raw_pairs = config_data.get("symbol_pairs", [])
        if config_data.get("symbol_pairs_use", False) is False:
            raw_pairs = []

        self.symbol_pairs: List[tuple] = []
        seen_pairs = set()
        for p in raw_pairs:
            if isinstance(p, dict):
                target_name, ref_name = p.get("target"), p.get("ref")
            else:  # [target, ref] の2要素配列
                if len(p) != 2:
                    raise ValueError(f"symbol_pairs の要素が不正です: {p!r}")
                target_name, ref_name = p[0], p[1]
            if target_name is None or ref_name is None:
                raise ValueError(
                    f"symbol_pairs の要素には target と ref が必要です: {p!r}"
                )
            for name in (target_name, ref_name):
                if name not in self.symbols:
                    raise ValueError(f"symbol_pairs に未定義の銘柄があります: {name}")

            pair = (ref_name, target_name)  # task順 (ref, target)
            if pair in seen_pairs:
                raise ValueError(
                    f"symbol_pairs に重複があります: "
                    f"target={target_name}, ref={ref_name}"
                )
            seen_pairs.add(pair)
            self.symbol_pairs.append(pair)

        if self.symbol_pairs:
            # 名指しモード: キャッシュ生成と検証がそのまま効くよう ref/target を絞る。
            # 定義順ではなく登場順で一意化する。
            self.ref_list: List[str] = list(
                dict.fromkeys(r for r, t in self.symbol_pairs)
            )
            self.target_list: List[str] = list(
                dict.fromkeys(t for r, t in self.symbol_pairs)
            )
        else:
            self.ref_list = self._build_symbol_list(
                self.ref_symbol_groups,
                self.ref_symbol_names,
                "ref",
            )
            self.target_list = self._build_symbol_list(
                self.target_symbol_groups,
                self.target_symbol_names,
                "target",
            )

            # target だけに適用する除外。ref 側には影響させない。
            undefined_excludes = [
                name for name in self.target_exclude_names
                if name not in self.symbols
            ]
            if undefined_excludes:
                raise ValueError(
                    "target_exclude_names に symbols 未定義の銘柄があります: "
                    + ", ".join(undefined_excludes)
                )

            excluded = set(self.target_exclude_names)
            self.target_list = [
                name for name in self.target_list
                if name not in excluded
            ]
            if not self.target_list:
                raise ValueError(
                    "target_symbol_groups / target_symbol_names / "
                    "target_exclude_names の指定により target が空です。"
                )

        raw_signal_types = config_data.get("signal_type_list", [])
        try:
            self.signal_type_list: List[SignalType] = [
                SignalType(value) for value in raw_signal_types
            ]
        except ValueError as exc:
            allowed = ", ".join(item.value for item in SignalType)
            raise ValueError(
                "signal_type_list に未対応の指標があります。"
                f"指定可能: {allowed}"
            ) from exc
        self.hold_days_list: List[int] = config_data.get("hold_days_list", [])
        self.start_days_list: List[int] = config_data.get("start_days_list", [])
        self.sma_period_list: List[int] = config_data.get("sma_period_list", [])
        # 一律の追加コスト（%／取引）。現実の摩擦（スプレッド変動・スリッページ・
        # 約定ズレ）の上乗せ分を、全銘柄まとめて検証するためのつまみ。
        # 各トレードの損益から entry 価格の extra_cost_pct% を引く（long/short 問わず）。
        # 0.0 なら従来どおり影響なし。値を振って main.py / walkforward.py を回すと、
        # 「摩擦をどこまで乗せても期待値がプラスで残るか」を選抜込みで検証できる。
        self.extra_cost_pct: float = config_data.get("extra_cost_pct", 0.0)
        raw_trade_code_type = config_data.get(
            "trade_code_type", TradeCodeType.ALL
        )
        try:
            self.trade_code_type: TradeCodeType = TradeCodeType(
                raw_trade_code_type
            )
        except ValueError as exc:
            allowed = ", ".join(item.value for item in TradeCodeType)
            raise ValueError(
                f"trade_code_type は次のいずれかを指定してください: {allowed}。"
                f"指定値: {raw_trade_code_type!r}"
            ) from exc
        self.min_trade_count: int = config_data.get("min_trade_count", 10)
        self.counter_trade: List[bool] = config_data.get("counter_trade", [False])
        self.use_process_pool: bool = config_data.get("use_process_pool", True)
        # 1タスクの実行時間をCSVに出力する。
        # 実行ごとに値が変わるため、回帰テスト用のGoldenを作るときはFalseにする。
        self.output_task_time: bool = config_data.get("output_task_time", False)
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
        # main.py のランキング集計の対象期間 [開始年, 終了年]。
        # 空/未指定なら全期間で t値・average・trade_count を計算する（従来どおり）。
        # 例 [2015, 2026] とすると 2015〜2026 のトレードだけで順位付けする。
        # 「昔は弱いが後半で伸びた」候補を上位に出すための機能。
        # 期間別列（period_years）は常に全期間で出るので、前半の弱さも同時に見える。
        # walkforward には影響しない（main.py のランキングのみ）。
        self.ranking_period: List[int] = config_data.get("ranking_period", [])
        if self.ranking_period:
            if len(self.ranking_period) != 2:
                raise ValueError(
                    "ranking_period は [開始年, 終了年] の2要素で指定してください。"
                )
            if self.ranking_period[0] > self.ranking_period[1]:
                raise ValueError("ranking_period は 開始年 <= 終了年 で指定してください。")

    @staticmethod
    def _validate_symbol_groups(
        groups: List[str],
        field_name: str,
        defined_groups: set,
    ) -> None:
        unknown_groups = [
            group for group in groups
            if group not in defined_groups
        ]
        if unknown_groups:
            raise ValueError(
                f"{field_name} に symbols 未定義のグループがあります: "
                + ", ".join(unknown_groups)
                + "（定義済み: "
                + ", ".join(sorted(defined_groups))
                + "）"
            )

    def _build_symbol_list(
        self,
        groups: List[str],
        names: List[str],
        role_name: str,
    ) -> List[str]:
        """group と個別指定から、symbols の定義順を保って銘柄一覧を作る。"""
        wanted_groups = set(groups)
        selected: List[str] = [
            name for name, value in self.symbols.items()
            if isinstance(value, dict) and value.get("group") in wanted_groups
        ]

        undefined_names = [
            name for name in names
            if name not in self.symbols
        ]
        if undefined_names:
            raise ValueError(
                f"{role_name}_symbol_names に symbols 未定義の銘柄があります: "
                + ", ".join(undefined_names)
            )

        for name in names:
            if name not in selected:
                selected.append(name)

        if not selected:
            raise ValueError(
                f"{role_name}_symbol_groups か {role_name}_symbol_names で "
                f"{role_name} 銘柄を指定してください。"
            )

        return selected

    def iter_ref_target(self):
        """(ref, target) を列挙する。
        symbol_pairs があればそのペアだけ、無ければ ref_list × target_list の総当たり。"""
        if self.symbol_pairs:
            yield from self.symbol_pairs
        else:
            for ref_name in self.ref_list:
                for target_name in self.target_list:
                    yield (ref_name, target_name)

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

    def widths_of(self, signal_type: SignalType) -> list:
        """指標に対応する閾値の候補を一覧で返す。
        config に数値を書けば1件、リストを書けばその全件を試せる。
        例: bb = [1.0, 1.5, 2.0] と書くと3通りを別々のタスクとして回す。"""
        value = self.threshold_width.get(signal_type, self.default_threshold_width)
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    def center_of(self, signal_type: SignalType) -> float:
        """指標に対応する中心値を返す。未設定なら 0。"""
        return self.threshold_center.get(signal_type, 0.0)

