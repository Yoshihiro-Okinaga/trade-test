from dataclasses import dataclass


@dataclass(frozen=True)
class PairResearchConfig:
    """相関・平均回帰研究で使う設定。

    [pair_research] が無い場合は、既存 config.toml の symbol_groups /
    symbol_names / exclude_names / ranking_period を再利用する。
    symbol_pairs は意図的に使わない。固定ペア検証では [pair_research].pairs を使う。
    """

    start_year: int | None
    end_year: int | None
    hedge_fit_start_year: int | None
    hedge_fit_end_year: int | None
    symbol_groups: tuple[str, ...]
    symbol_names: tuple[str, ...]
    exclude_names: tuple[str, ...]
    pairs: tuple[tuple[str, str], ...]

    min_observations: int
    rolling_window: int
    z_lookback: int
    z_thresholds: tuple[float, ...]
    revert_horizons: tuple[int, ...]

    # pair_study.py で使っていた「実用候補」の基準。
    # CSVから行を捨てるためではなく、コンソールの参考候補表示だけに使う。
    candidate_min_abs_correlation: float
    candidate_half_life_min: float
    candidate_half_life_max: float
    candidate_mean_reversion_t_max: float
    candidate_z_threshold: float
    candidate_edge_horizon: int
    candidate_min_events: int

    @classmethod
    def from_config_data(cls, config_data: dict) -> "PairResearchConfig":
        section = config_data.get("pair_research", {})

        period = section.get("period")
        if period is None:
            period = config_data.get("ranking_period", [])

        start_year, end_year = cls._parse_period(
            period,
            "pair_research.period / ranking_period",
        )
        (
            hedge_fit_start_year,
            hedge_fit_end_year,
        ) = cls._parse_period(
            section.get("hedge_fit_period", []),
            "pair_research.hedge_fit_period",
        )

        symbol_groups = tuple(
            section.get(
                "symbol_groups",
                config_data.get("symbol_groups", []),
            )
        )
        symbol_names = tuple(
            section.get(
                "symbol_names",
                config_data.get("symbol_names", []),
            )
        )
        exclude_names = tuple(
            section.get(
                "exclude_names",
                config_data.get("exclude_names", []),
            )
        )
        pairs = cls._parse_pairs(
            section.get("pairs", [])
        )

        config = cls(
            start_year=start_year,
            end_year=end_year,
            hedge_fit_start_year=hedge_fit_start_year,
            hedge_fit_end_year=hedge_fit_end_year,
            symbol_groups=symbol_groups,
            symbol_names=symbol_names,
            exclude_names=exclude_names,
            pairs=pairs,
            min_observations=int(
                section.get("min_observations", 500)
            ),
            rolling_window=int(
                section.get("rolling_window", 252)
            ),
            z_lookback=int(
                section.get("z_lookback", 60)
            ),
            z_thresholds=tuple(
                float(value)
                for value in section.get(
                    "z_thresholds",
                    [1.5, 2.0, 2.5],
                )
            ),
            revert_horizons=tuple(
                int(value)
                for value in section.get(
                    "revert_horizons",
                    [5, 10, 20, 40],
                )
            ),
            candidate_min_abs_correlation=float(
                section.get(
                    "candidate_min_abs_correlation",
                    0.5,
                )
            ),
            candidate_half_life_min=float(
                section.get(
                    "candidate_half_life_min",
                    5.0,
                )
            ),
            candidate_half_life_max=float(
                section.get(
                    "candidate_half_life_max",
                    60.0,
                )
            ),
            candidate_mean_reversion_t_max=float(
                section.get(
                    "candidate_mean_reversion_t_max",
                    -2.9,
                )
            ),
            candidate_z_threshold=float(
                section.get(
                    "candidate_z_threshold",
                    2.0,
                )
            ),
            candidate_edge_horizon=int(
                section.get(
                    "candidate_edge_horizon",
                    20,
                )
            ),
            candidate_min_events=int(
                section.get(
                    "candidate_min_events",
                    20,
                )
            ),
        )
        config._validate()
        return config

    @staticmethod
    def _parse_pairs(
        pairs,
    ) -> tuple[tuple[str, str], ...]:
        if not pairs:
            return ()

        parsed = []
        seen = set()

        for index, pair in enumerate(pairs, start=1):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(
                    "pair_research.pairs の各要素は "
                    "[銘柄A, 銘柄B] の2要素で指定してください。"
                    f" index={index}"
                )

            symbol_a = str(pair[0])
            symbol_b = str(pair[1])
            if symbol_a == symbol_b:
                raise ValueError(
                    "pair_research.pairs に同一銘柄のペアがあります: "
                    f"{symbol_a}"
                )

            pair_key = frozenset((symbol_a, symbol_b))
            if pair_key in seen:
                raise ValueError(
                    "pair_research.pairs に重複ペアがあります: "
                    f"{symbol_a} / {symbol_b}"
                )

            seen.add(pair_key)
            parsed.append((symbol_a, symbol_b))

        return tuple(parsed)


    @staticmethod
    def _parse_period(
        period,
        field_name: str,
    ) -> tuple[int | None, int | None]:
        if not period:
            return None, None
        if len(period) != 2:
            raise ValueError(
                f"{field_name} は "
                "[開始年, 終了年] の2要素で指定してください。"
            )

        start_year = int(period[0])
        end_year = int(period[1])
        if start_year > end_year:
            raise ValueError(
                f"{field_name} は "
                "開始年 <= 終了年 で指定してください。"
            )
        return start_year, end_year

    @property
    def uses_fixed_hedge(self) -> bool:
        return self.hedge_fit_start_year is not None

    def _validate(self) -> None:
        if self.uses_fixed_hedge:
            if self.start_year is None or self.end_year is None:
                raise ValueError(
                    "hedge_fit_period を使う場合は "
                    "pair_research.period も指定してください。"
                )
            if self.hedge_fit_end_year >= self.start_year:
                raise ValueError(
                    "hedge_fit_period は評価期間より前にしてください。"
                    f" fit_end={self.hedge_fit_end_year}, "
                    f"period_start={self.start_year}"
                )

        if self.min_observations < 30:
            raise ValueError(
                "min_observations は30以上を指定してください。"
            )
        if self.rolling_window < 20:
            raise ValueError(
                "rolling_window は20以上を指定してください。"
            )
        if self.z_lookback < 20:
            raise ValueError(
                "z_lookback は20以上を指定してください。"
            )
        if not self.z_thresholds:
            raise ValueError(
                "z_thresholds は1つ以上指定してください。"
            )
        if any(value <= 0 for value in self.z_thresholds):
            raise ValueError(
                "z_thresholds は0より大きい値を指定してください。"
            )
        if not self.revert_horizons:
            raise ValueError(
                "revert_horizons は1つ以上指定してください。"
            )
        if any(value < 1 for value in self.revert_horizons):
            raise ValueError(
                "revert_horizons は1以上を指定してください。"
            )

        if not 0 <= self.candidate_min_abs_correlation <= 1:
            raise ValueError(
                "candidate_min_abs_correlation は "
                "0〜1で指定してください。"
            )
        if self.candidate_half_life_min <= 0:
            raise ValueError(
                "candidate_half_life_min は0より大きくしてください。"
            )
        if (
            self.candidate_half_life_max
            < self.candidate_half_life_min
        ):
            raise ValueError(
                "candidate_half_life_max は "
                "candidate_half_life_min 以上にしてください。"
            )
        if self.candidate_z_threshold not in self.z_thresholds:
            raise ValueError(
                "candidate_z_threshold は z_thresholds に "
                "含まれる値を指定してください。"
            )
        if self.candidate_edge_horizon not in self.revert_horizons:
            raise ValueError(
                "candidate_edge_horizon は revert_horizons に "
                "含まれる値を指定してください。"
            )
        if self.candidate_min_events < 1:
            raise ValueError(
                "candidate_min_events は1以上を指定してください。"
            )

    def build_universe(
        self,
        config_data: dict,
    ) -> list[str]:
        """設定から研究対象銘柄を定義順で作る。

        pairs が指定されている場合は、その固定ペアに必要な銘柄だけを返す。
        pairs が空なら従来通り symbol_groups / symbol_names から作る。
        """
        symbols = config_data.get("symbols", {})
        if not isinstance(symbols, dict) or not symbols:
            raise ValueError(
                "config.toml に [symbols] がありません。"
            )

        if self.pairs:
            pair_names = []
            for symbol_a, symbol_b in self.pairs:
                for name in (symbol_a, symbol_b):
                    if name not in symbols:
                        raise ValueError(
                            "pair_research.pairs の未定義銘柄: "
                            f"{name}"
                        )
                    if name not in pair_names:
                        pair_names.append(name)
            return pair_names

        defined_groups = {
            value.get("group")
            for value in symbols.values()
            if isinstance(value, dict)
            and value.get("group")
        }
        unknown_groups = [
            group
            for group in self.symbol_groups
            if group not in defined_groups
        ]
        if unknown_groups:
            raise ValueError(
                "pair_research の未定義グループ: "
                + ", ".join(unknown_groups)
            )

        unknown_names = [
            name
            for name in self.symbol_names
            if name not in symbols
        ]
        if unknown_names:
            raise ValueError(
                "pair_research の未定義銘柄: "
                + ", ".join(unknown_names)
            )

        wanted_groups = set(self.symbol_groups)
        selected = [
            name
            for name, value in symbols.items()
            if (
                isinstance(value, dict)
                and value.get("group") in wanted_groups
            )
        ]

        for name in self.symbol_names:
            if name not in selected:
                selected.append(name)

        excluded = set(self.exclude_names)
        selected = [
            name
            for name in selected
            if name not in excluded
        ]

        if len(selected) < 2:
            raise ValueError(
                "相関ペア研究には2銘柄以上必要です。"
                "symbol_groups / symbol_names を確認してください。"
            )

        return selected
