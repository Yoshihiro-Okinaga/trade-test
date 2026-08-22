from dataclasses import dataclass


@dataclass
class WalkForwardConfig:
    train_years: int
    test_years: int
    step_years: int
    mode: str
    select_metric: str
    select_per: str
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
            mode=wf.get("mode", "anchored"),
            select_metric=wf.get("select_metric", "t_value"),
            select_per=wf.get("select_per", "target"),
            select_top_k=int(wf.get("select_top_k", 1)),
            min_is_trades=int(wf.get("min_is_trades", 30)),
            # 品質ゲート: 各銘柄の最良候補でも学習期間の t値がこの値未満なら、
            # その銘柄はその期間は見送る（張らない）。0.0 でゲート無効＝従来どおり。
            min_is_t=float(wf.get("min_is_t", 0.0)),
            # ポートフォリオ全体の同時建玉数。0 は無制限。
            max_open_positions=int(wf.get("max_open_positions", 0)),
        )
