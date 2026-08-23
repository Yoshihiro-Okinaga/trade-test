from dataclasses import dataclass
import math
import warnings

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.stattools import adfuller, coint
except ImportError as exc:
    raise ImportError(
        "pair_research には statsmodels が必要です。"
        "未導入なら `pip install statsmodels` を実行してください。"
    ) from exc


@dataclass(frozen=True)
class ForwardConvergenceStatistics:
    mean_pct: float
    median_pct: float
    positive_rate: float


@dataclass(frozen=True)
class ReversionStatistics:
    event_count: int
    rates: dict[int, float]
    convergence: dict[int, ForwardConvergenceStatistics]


@dataclass(frozen=True)
class CurrencyOverlap:
    shared_currency: str
    overlap_type: str
    effective_pair_if_beta_1: str


@dataclass(frozen=True)
class PairStatistics:
    symbol_a: str
    symbol_b: str
    start_date: str
    end_date: str
    observation_count: int

    return_correlation: float
    rolling_corr_mean: float
    rolling_corr_min: float
    rolling_corr_std: float

    hedge_alpha: float
    hedge_ratio: float
    spread_std: float

    adf_stat: float
    adf_p_value: float
    coint_p_value_ab: float
    coint_p_value_ba: float
    coint_p_value_worst: float

    mean_reversion_beta: float
    mean_reversion_t: float
    half_life_days: float
    zero_crossings: int

    shared_currency: str
    currency_overlap_type: str
    effective_pair_if_beta_1: str

    reversion: dict[float, ReversionStatistics]

    def to_row(
        self,
        z_thresholds: tuple[float, ...],
        revert_horizons: tuple[int, ...],
    ) -> dict:
        row = {
            "status": "ok",
            "message": "",
            "symbol_a": self.symbol_a,
            "symbol_b": self.symbol_b,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "observation_count": self.observation_count,
            "return_correlation": self.return_correlation,
            "rolling_corr_mean": self.rolling_corr_mean,
            "rolling_corr_min": self.rolling_corr_min,
            "rolling_corr_std": self.rolling_corr_std,
            "hedge_alpha": self.hedge_alpha,
            "hedge_ratio": self.hedge_ratio,
            "hedge_ratio_distance_from_1": abs(
                self.hedge_ratio - 1.0
            ),
            "spread_std": self.spread_std,
            "adf_stat": self.adf_stat,
            "adf_p_value": self.adf_p_value,
            "coint_p_value_ab": self.coint_p_value_ab,
            "coint_p_value_ba": self.coint_p_value_ba,
            "coint_p_value_worst": self.coint_p_value_worst,
            "mean_reversion_beta": self.mean_reversion_beta,
            "mean_reversion_t": self.mean_reversion_t,
            "half_life_days": self.half_life_days,
            "zero_crossings": self.zero_crossings,
            "shared_currency": self.shared_currency,
            "currency_overlap_type": self.currency_overlap_type,
            "effective_pair_if_beta_1": (
                self.effective_pair_if_beta_1
            ),
        }

        for threshold in z_thresholds:
            stats = self.reversion[threshold]
            prefix = z_prefix(threshold)
            row[f"{prefix}_count"] = stats.event_count

            for horizon in revert_horizons:
                row[
                    f"{prefix}_revert_{horizon}d"
                ] = stats.rates[horizon]

                edge = stats.convergence[horizon]
                row[
                    f"{prefix}_edge_{horizon}d_mean_pct"
                ] = edge.mean_pct
                row[
                    f"{prefix}_edge_{horizon}d_median_pct"
                ] = edge.median_pct
                row[
                    f"{prefix}_edge_{horizon}d_positive_rate"
                ] = edge.positive_rate

        return row


def analyze_pair(
    symbol_a: str,
    df_a: pd.DataFrame,
    symbol_b: str,
    df_b: pd.DataFrame,
    *,
    start_year: int | None,
    end_year: int | None,
    min_observations: int,
    rolling_window: int,
    z_lookback: int,
    z_thresholds: tuple[float, ...],
    revert_horizons: tuple[int, ...],
) -> PairStatistics:
    aligned = align_prices(
        df_a,
        df_b,
        start_year=start_year,
        end_year=end_year,
    )

    if len(aligned) < min_observations:
        raise ValueError(
            "共通データが不足しています: "
            f"{len(aligned)} < {min_observations}"
        )

    log_a = np.log(
        aligned["price_a"].to_numpy(dtype=float)
    )
    log_b = np.log(
        aligned["price_b"].to_numpy(dtype=float)
    )

    if (
        not np.isfinite(log_a).all()
        or not np.isfinite(log_b).all()
    ):
        raise ValueError(
            "価格の対数変換で非有限値が発生しました。"
        )

    return_corr, rolling_stats = (
        calculate_return_correlations(
            log_a,
            log_b,
            rolling_window,
        )
    )

    hedge_alpha, hedge_ratio, spread = (
        calculate_spread(log_a, log_b)
    )
    spread_std = float(np.std(spread, ddof=1))
    if (
        not math.isfinite(spread_std)
        or spread_std <= 0
    ):
        raise ValueError(
            "spread の標準偏差を計算できません。"
        )

    adf_stat, adf_p_value = calculate_adf(spread)
    coint_ab, coint_ba = calculate_cointegration(
        log_a,
        log_b,
    )

    (
        mean_reversion_beta,
        mean_reversion_t,
        half_life,
    ) = calculate_mean_reversion_regression(spread)

    zero_crossings = count_zero_crossings(spread)

    # pair_study.py の良かった点を継承し、乖離イベントの
    # 発見には「その日まで」の移動平均・標準偏差を使う。
    z_score = calculate_rolling_z_score(
        spread,
        z_lookback,
    )

    reversion = {
        threshold: calculate_reversion_statistics(
            spread,
            z_score,
            threshold,
            revert_horizons,
        )
        for threshold in z_thresholds
    }

    currency_overlap = analyze_currency_overlap(
        symbol_a,
        symbol_b,
    )

    return PairStatistics(
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        start_date=(
            aligned["日付"]
            .iloc[0]
            .strftime("%Y-%m-%d")
        ),
        end_date=(
            aligned["日付"]
            .iloc[-1]
            .strftime("%Y-%m-%d")
        ),
        observation_count=len(aligned),
        return_correlation=return_corr,
        rolling_corr_mean=rolling_stats["mean"],
        rolling_corr_min=rolling_stats["min"],
        rolling_corr_std=rolling_stats["std"],
        hedge_alpha=hedge_alpha,
        hedge_ratio=hedge_ratio,
        spread_std=spread_std,
        adf_stat=adf_stat,
        adf_p_value=adf_p_value,
        coint_p_value_ab=coint_ab,
        coint_p_value_ba=coint_ba,
        coint_p_value_worst=max(
            coint_ab,
            coint_ba,
        ),
        mean_reversion_beta=mean_reversion_beta,
        mean_reversion_t=mean_reversion_t,
        half_life_days=half_life,
        zero_crossings=zero_crossings,
        shared_currency=(
            currency_overlap.shared_currency
        ),
        currency_overlap_type=(
            currency_overlap.overlap_type
        ),
        effective_pair_if_beta_1=(
            currency_overlap.effective_pair_if_beta_1
        ),
        reversion=reversion,
    )


def align_prices(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    start_year: int | None,
    end_year: int | None,
) -> pd.DataFrame:
    """2銘柄を共通営業日だけに揃える。"""
    left = (
        df_a[["日付", "終値"]]
        .rename(columns={"終値": "price_a"})
    )
    right = (
        df_b[["日付", "終値"]]
        .rename(columns={"終値": "price_b"})
    )

    aligned = pd.merge(
        left,
        right,
        on="日付",
        how="inner",
    )
    aligned = (
        aligned
        .sort_values("日付")
        .dropna()
    )

    if start_year is not None:
        aligned = aligned[
            aligned["日付"].dt.year >= start_year
        ]
    if end_year is not None:
        aligned = aligned[
            aligned["日付"].dt.year <= end_year
        ]

    if (
        aligned[["price_a", "price_b"]]
        <= 0
    ).any().any():
        raise ValueError(
            "0以下の終値が含まれているため"
            "対数価格を使えません。"
        )

    return aligned.reset_index(drop=True)


def calculate_return_correlations(
    log_a: np.ndarray,
    log_b: np.ndarray,
    rolling_window: int,
) -> tuple[float, dict[str, float]]:
    """日次対数リターン相関とローリング相関を返す。"""
    return_a = pd.Series(log_a).diff()
    return_b = pd.Series(log_b).diff()

    return_correlation = float(
        return_a.corr(return_b)
    )

    rolling = return_a.rolling(
        rolling_window,
        min_periods=rolling_window,
    ).corr(return_b)
    rolling = rolling.dropna()

    if rolling.empty:
        rolling_stats = {
            "mean": float("nan"),
            "min": float("nan"),
            "std": float("nan"),
        }
    else:
        rolling_stats = {
            "mean": float(rolling.mean()),
            "min": float(rolling.min()),
            "std": float(
                rolling.std(ddof=1)
            ),
        }

    return return_correlation, rolling_stats


def calculate_spread(
    log_a: np.ndarray,
    log_b: np.ndarray,
) -> tuple[float, float, np.ndarray]:
    """log(A) = alpha + beta * log(B) のOLS残差をspreadとする。"""
    x = np.column_stack(
        [np.ones(len(log_b)), log_b]
    )
    coefficients, *_ = np.linalg.lstsq(
        x,
        log_a,
        rcond=None,
    )

    alpha = float(coefficients[0])
    beta = float(coefficients[1])
    spread = log_a - (
        alpha + beta * log_b
    )
    return alpha, beta, spread


def calculate_adf(
    spread: np.ndarray,
) -> tuple[float, float]:
    """spread が単位根を持つという帰無仮説をADFで検定する。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = adfuller(
            spread,
            autolag="AIC",
        )
    return float(result[0]), float(result[1])


def calculate_cointegration(
    log_a: np.ndarray,
    log_b: np.ndarray,
) -> tuple[float, float]:
    """Engle-Grangerを両方向で行い、それぞれのp値を返す。

    回帰方向による結果差を隠さないため、
    A←B と B←A の両方を残す。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _stat_ab, p_ab, _critical_ab = coint(
            log_a,
            log_b,
            trend="c",
            autolag="aic",
        )
        _stat_ba, p_ba, _critical_ba = coint(
            log_b,
            log_a,
            trend="c",
            autolag="aic",
        )

    return float(p_ab), float(p_ba)


def calculate_mean_reversion_regression(
    spread: np.ndarray,
) -> tuple[float, float, float]:
    """平均回帰係数、そのt値、half-lifeを返す。

    pair_study.py と同じ考え方で、
        Δs_t = a + b * s_(t-1) + e
    をOLSで推定する。

    b < 0 ならspreadが高いと次に下がる方向。
    AR(1)係数 phi = 1 + b として、
        half-life = -ln(2) / ln(phi)
    を使う。以前の近似 -ln(2)/b より厳密。
    """
    lagged = spread[:-1]
    delta = np.diff(spread)

    x = np.column_stack(
        [np.ones(len(lagged)), lagged]
    )
    coefficients, *_ = np.linalg.lstsq(
        x,
        delta,
        rcond=None,
    )

    beta = float(coefficients[1])
    fitted = x @ coefficients
    residual = delta - fitted

    dof = len(delta) - x.shape[1]
    if dof <= 0:
        return (
            beta,
            float("nan"),
            float("nan"),
        )

    sigma2 = float(
        residual @ residual / dof
    )
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta_variance = (
        sigma2 * xtx_inv[1, 1]
    )
    beta_se = (
        math.sqrt(beta_variance)
        if beta_variance > 0
        else float("nan")
    )
    beta_t = (
        beta / beta_se
        if math.isfinite(beta_se)
        and beta_se > 0
        else float("nan")
    )

    phi = 1.0 + beta
    if not 0.0 < phi < 1.0:
        half_life = float("nan")
    else:
        half_life = (
            -math.log(2.0)
            / math.log(phi)
        )

    return (
        beta,
        float(beta_t),
        float(half_life),
    )


def calculate_rolling_z_score(
    spread: np.ndarray,
    window: int,
) -> np.ndarray:
    """その日までのspreadだけで移動z-scoreを計算する。"""
    series = pd.Series(
        spread,
        dtype=float,
    )
    mean = series.rolling(
        window,
        min_periods=window,
    ).mean()
    std = series.rolling(
        window,
        min_periods=window,
    ).std(ddof=1)
    z_score = (
        (series - mean)
        / std.replace(0, np.nan)
    )
    return z_score.to_numpy(dtype=float)


def count_zero_crossings(
    spread: np.ndarray,
) -> int:
    """spread がOLS残差の0を跨いだ回数を返す。"""
    signs = np.sign(spread)
    nonzero_signs = signs[signs != 0]

    if len(nonzero_signs) < 2:
        return 0

    return int(
        np.sum(
            nonzero_signs[1:]
            != nonzero_signs[:-1]
        )
    )


def calculate_reversion_statistics(
    spread: np.ndarray,
    z_score: np.ndarray,
    threshold: float,
    horizons: tuple[int, ...],
) -> ReversionStatistics:
    """独立した乖離イベントについて回帰率と縮小幅を測る。

    1回の乖離はz=0へ戻るまで1イベントとして扱う。
    全horizonで同じ分母を使うため、最大horizonぶん
    将来を観測できるイベントだけを集計する。

    edgeは「OLS log-spreadが、そのポジション方向に
    何%ポイント縮んだか」を表す。実際の売買コストや
    資金配分を含む損益率ではない。
    """
    max_horizon = max(horizons)
    events = find_excursion_starts(
        z_score,
        threshold,
    )
    eligible_events = [
        (index, direction)
        for index, direction in events
        if index + max_horizon < len(z_score)
    ]

    rates = {}
    convergence = {}

    for horizon in horizons:
        reverted = sum(
            1
            for index, direction in eligible_events
            if reverted_within(
                z_score,
                index,
                direction,
                horizon,
            )
        )
        rates[horizon] = (
            reverted / len(eligible_events)
            if eligible_events
            else float("nan")
        )

        edge_values = [
            convergence_edge_pct(
                spread,
                index,
                direction,
                horizon,
            )
            for index, direction in eligible_events
        ]

        if edge_values:
            values = np.asarray(
                edge_values,
                dtype=float,
            )
            convergence[horizon] = (
                ForwardConvergenceStatistics(
                    mean_pct=float(
                        np.mean(values)
                    ),
                    median_pct=float(
                        np.median(values)
                    ),
                    positive_rate=float(
                        np.mean(values > 0)
                    ),
                )
            )
        else:
            convergence[horizon] = (
                ForwardConvergenceStatistics(
                    mean_pct=float("nan"),
                    median_pct=float("nan"),
                    positive_rate=float("nan"),
                )
            )

    return ReversionStatistics(
        event_count=len(eligible_events),
        rates=rates,
        convergence=convergence,
    )


def find_excursion_starts(
    z_score: np.ndarray,
    threshold: float,
) -> list[tuple[int, int]]:
    """独立した乖離イベントの開始位置と方向を返す。"""
    events = []
    in_excursion = False
    direction = 0

    for index, value in enumerate(z_score):
        if not math.isfinite(float(value)):
            continue

        if not in_excursion:
            if value >= threshold:
                events.append((index, 1))
                in_excursion = True
                direction = 1
            elif value <= -threshold:
                events.append((index, -1))
                in_excursion = True
                direction = -1
            continue

        if direction > 0 and value <= 0:
            in_excursion = False
            direction = 0
        elif direction < 0 and value >= 0:
            in_excursion = False
            direction = 0

    return events


def reverted_within(
    z_score: np.ndarray,
    start_index: int,
    direction: int,
    horizon: int,
) -> bool:
    """乖離開始後horizon営業日以内に移動平均へ戻ったか。"""
    end_index = min(
        start_index + horizon,
        len(z_score) - 1,
    )
    future = z_score[
        start_index + 1:end_index + 1
    ]

    if direction > 0:
        return bool(np.any(future <= 0))
    return bool(np.any(future >= 0))


def convergence_edge_pct(
    spread: np.ndarray,
    start_index: int,
    direction: int,
    horizon: int,
) -> float:
    """horizon日後にspreadが乖離方向と逆へ何%縮んだか。

    spreadは対数なので差×100を%相当として表示する。
    正なら乖離方向に対する逆張りが有利な方向へ動いた。
    """
    start_value = float(
        spread[start_index]
    )
    future_value = float(
        spread[start_index + horizon]
    )

    if direction > 0:
        edge = start_value - future_value
    else:
        edge = future_value - start_value

    return edge * 100.0


def analyze_currency_overlap(
    symbol_a: str,
    symbol_b: str,
) -> CurrencyOverlap:
    """FXペアの共通通貨と、単純相殺できる関係かを調べる。

    pair_study.py の「共通通貨を見る」という発想を継承するが、
    共通通貨があるだけでは相殺とはみなさない。

    log(A) - log(B) を考えたとき、
    共通通貨が両方で同じ側（base-base / quote-quote）なら、
    hedge ratio が1のときにその通貨が相殺される。

    例:
        AUD_JPY - NZD_JPY -> AUD_NZD
        EUR_USD - EUR_GBP -> GBP_USD

    反対側にある場合は単純相殺ではない。
    例:
        EUR_GBP - GBP_USD
    """
    pair_a = parse_fx_pair(symbol_a)
    pair_b = parse_fx_pair(symbol_b)

    if pair_a is None or pair_b is None:
        return CurrencyOverlap("", "", "")

    common = set(pair_a) & set(pair_b)
    if not common:
        return CurrencyOverlap("", "", "")

    if len(common) == 2:
        if pair_a == pair_b:
            overlap_type = "same_pair"
        elif pair_a == pair_b[::-1]:
            overlap_type = "inverse_pair"
        else:
            overlap_type = "two_shared"
        return CurrencyOverlap(
            shared_currency="/".join(
                sorted(common)
            ),
            overlap_type=overlap_type,
            effective_pair_if_beta_1="",
        )

    shared = next(iter(common))
    position_a = (
        "base"
        if pair_a[0] == shared
        else "quote"
    )
    position_b = (
        "base"
        if pair_b[0] == shared
        else "quote"
    )

    if position_a != position_b:
        return CurrencyOverlap(
            shared_currency=shared,
            overlap_type=(
                f"opposite_side:"
                f"{position_a}-{position_b}"
            ),
            effective_pair_if_beta_1="",
        )

    other_a = (
        pair_a[1]
        if position_a == "base"
        else pair_a[0]
    )
    other_b = (
        pair_b[1]
        if position_b == "base"
        else pair_b[0]
    )

    if position_a == "quote":
        effective_pair = (
            f"{other_a}_{other_b}"
        )
    else:
        effective_pair = (
            f"{other_b}_{other_a}"
        )

    return CurrencyOverlap(
        shared_currency=shared,
        overlap_type=(
            f"same_side:{position_a}"
        ),
        effective_pair_if_beta_1=(
            effective_pair
        ),
    )


def parse_fx_pair(
    symbol_name: str,
) -> tuple[str, str] | None:
    """AAA_BBB 形式のFX名だけを(base, quote)として返す。"""
    parts = symbol_name.split("_")
    if len(parts) != 2:
        return None

    if not all(
        len(part) == 3
        and part.isalpha()
        and part.isupper()
        for part in parts
    ):
        return None

    return parts[0], parts[1]


def z_prefix(
    threshold: float,
) -> str:
    text = (
        f"{threshold:g}"
        .replace(".", "_")
    )
    return f"z{text}"
