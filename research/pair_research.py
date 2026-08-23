import argparse
import datetime
from itertools import combinations
from pathlib import Path
import sys
import tomllib


# このファイルをサブフォルダから直接実行しても、
# プロジェクト直下の market_data.py を読めるようにする。
PAIR_RESEARCH_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PAIR_RESEARCH_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import pandas as pd

from market_data import MarketData
from pair_research_config import PairResearchConfig
from pair_statistics import analyze_pair, z_prefix


OUTPUT_FILE_NAME = "pair_research.csv"


def default_save_dir() -> Path:
    """既存の分析プログラムと同じ通常出力先を返す。"""
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Dropbox"
            / "Private"
            / "trade_test_results"
        )
    return Path("./")


def load_config(
    config_path: Path,
) -> dict:
    try:
        with open(config_path, "rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"config.toml が見つかりません: "
            f"{config_path}"
        ) from None


def load_price_data(
    symbol_names: list[str],
    data_folder=None,
) -> dict[str, pd.DataFrame]:
    """研究対象銘柄の価格データを1回ずつ読み込む。"""
    price_data = {}

    for index, symbol_name in enumerate(
        symbol_names,
        start=1,
    ):
        print(
            f"\r価格読み込み: "
            f"{index}/{len(symbol_names)} "
            f"{symbol_name:<24}",
            end="",
            flush=True,
        )

        price_data[symbol_name] = MarketData(
            symbol_name,
            data_folder,
        ).df[["日付", "終値"]].copy()

    print()
    return price_data


def research_pairs(
    symbol_names: list[str],
    price_data: dict[str, pd.DataFrame],
    config: PairResearchConfig,
) -> list[dict]:
    """全ペアを調べ、CSVに書けるdictのリストを返す。"""
    pairs = list(
        combinations(symbol_names, 2)
    )
    rows = []

    for index, (
        symbol_a,
        symbol_b,
    ) in enumerate(pairs, start=1):
        print(
            f"\rペア分析: "
            f"{index}/{len(pairs)} "
            f"{symbol_a} / {symbol_b:<24}",
            end="",
            flush=True,
        )

        try:
            statistics = analyze_pair(
                symbol_a,
                price_data[symbol_a],
                symbol_b,
                price_data[symbol_b],
                start_year=config.start_year,
                end_year=config.end_year,
                min_observations=(
                    config.min_observations
                ),
                rolling_window=(
                    config.rolling_window
                ),
                z_lookback=config.z_lookback,
                z_thresholds=(
                    config.z_thresholds
                ),
                revert_horizons=(
                    config.revert_horizons
                ),
            )
            row = statistics.to_row(
                config.z_thresholds,
                config.revert_horizons,
            )
        except Exception as exc:
            row = error_row(
                symbol_a,
                symbol_b,
                str(exc),
            )

        rows.append(row)

    print()
    return rows


def error_row(
    symbol_a: str,
    symbol_b: str,
    message: str,
) -> dict:
    return {
        "status": "error",
        "message": message,
        "symbol_a": symbol_a,
        "symbol_b": symbol_b,
    }


def sort_results(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """総合点は作らず、統計検定→相関の順で見やすく並べる。"""
    if df.empty:
        return df

    result = df.copy()
    result["_status_order"] = result[
        "status"
    ].map(
        {"ok": 0, "error": 1}
    ).fillna(2)

    for column in [
        "coint_p_value_worst",
        "adf_p_value",
    ]:
        if column not in result.columns:
            result[column] = float("nan")

    if "return_correlation" in result.columns:
        result["_abs_correlation"] = (
            pd.to_numeric(
                result["return_correlation"],
                errors="coerce",
            ).abs()
        )
    else:
        result["_abs_correlation"] = (
            float("nan")
        )

    result = result.sort_values(
        [
            "_status_order",
            "coint_p_value_worst",
            "adf_p_value",
            "_abs_correlation",
            "symbol_a",
            "symbol_b",
        ],
        ascending=[
            True,
            True,
            True,
            False,
            True,
            True,
        ],
        na_position="last",
    )

    return result.drop(
        columns=[
            "_status_order",
            "_abs_correlation",
        ]
    ).reset_index(drop=True)


def print_summary(
    df: pd.DataFrame,
    config: PairResearchConfig,
) -> None:
    successful = df[
        df["status"] == "ok"
    ].copy()

    if successful.empty:
        print(
            "有効な研究結果がありませんでした。"
        )
        return

    strict = successful[
        (successful["adf_p_value"] <= 0.05)
        & (
            successful[
                "coint_p_value_worst"
            ] <= 0.05
        )
    ]

    period_text = (
        f"{config.start_year}〜"
        f"{config.end_year}"
        if config.start_year is not None
        else "全期間"
    )

    print("\n=== 相関ペア研究 ===")
    print(
        f"研究期間              : "
        f"{period_text}"
    )
    print(
        f"有効ペア数            : "
        f"{len(successful):,}"
    )
    print(
        "ADF p<=0.05 かつ "
        "両方向cointegration p<=0.05: "
        f"{len(strict):,}"
    )

    if not strict.empty:
        print(
            "\n■ 統計条件を満たした先頭15ペア"
        )
        columns = [
            "symbol_a",
            "symbol_b",
            "return_correlation",
            "adf_p_value",
            "coint_p_value_worst",
            "mean_reversion_t",
            "half_life_days",
        ]
        print(
            strict[columns]
            .head(15)
            .to_string(index=False)
        )

    print_practical_candidates(
        successful,
        config,
    )


def print_practical_candidates(
    successful: pd.DataFrame,
    config: PairResearchConfig,
) -> None:
    """旧pair_studyの基準を参考表示として再現する。

    これは選抜・検証ではない。CSVから行を捨てず、
    「次に詳しく見る候補」をコンソールに出すだけ。
    """
    prefix = z_prefix(
        config.candidate_z_threshold
    )
    edge_column = (
        f"{prefix}_edge_"
        f"{config.candidate_edge_horizon}"
        "d_mean_pct"
    )
    count_column = f"{prefix}_count"

    required_columns = [
        "return_correlation",
        "half_life_days",
        "mean_reversion_t",
        edge_column,
        count_column,
    ]
    if any(
        column not in successful.columns
        for column in required_columns
    ):
        return

    candidates = successful[
        (
            successful[
                "return_correlation"
            ].abs()
            >= (
                config
                .candidate_min_abs_correlation
            )
        )
        & (
            successful["half_life_days"]
            >= config.candidate_half_life_min
        )
        & (
            successful["half_life_days"]
            <= config.candidate_half_life_max
        )
        & (
            successful["mean_reversion_t"]
            <= (
                config
                .candidate_mean_reversion_t_max
            )
        )
        & (
            successful[count_column]
            >= config.candidate_min_events
        )
        & (
            successful[edge_column] > 0
        )
    ].copy()

    candidates = candidates.sort_values(
        edge_column,
        ascending=False,
    )

    print(
        "\n■ 実用面の参考候補 "
        "（旧 pair_study 基準を改善して継承）"
    )
    print(
        "※ 探索上の目星であり、"
        "売買戦略の検証結果ではありません。"
    )
    print(
        f"条件: |corr|>="
        f"{config.candidate_min_abs_correlation:g}, "
        f"half-life="
        f"{config.candidate_half_life_min:g}"
        f"〜{config.candidate_half_life_max:g}日, "
        f"回帰t<="
        f"{config.candidate_mean_reversion_t_max:g}, "
        f"イベント>="
        f"{config.candidate_min_events}, "
        f"{config.candidate_edge_horizon}日edge>0"
    )
    print(
        f"候補数: {len(candidates):,}"
    )

    if candidates.empty:
        return

    columns = [
        "symbol_a",
        "symbol_b",
        "return_correlation",
        "half_life_days",
        "mean_reversion_t",
        count_column,
        edge_column,
        "shared_currency",
        "currency_overlap_type",
        "effective_pair_if_beta_1",
    ]
    print(
        candidates[columns]
        .head(20)
        .to_string(index=False)
    )


def run(
    config_path=None,
    data_folder=None,
    save_dir=None,
) -> Path:
    start_time = datetime.datetime.now()

    config_path = (
        Path(config_path)
        if config_path is not None
        else PROJECT_DIR / "config.toml"
    )
    save_dir = (
        Path(save_dir)
        if save_dir is not None
        else default_save_dir()
    )
    save_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    config_data = load_config(
        config_path
    )
    research_config = (
        PairResearchConfig.from_config_data(
            config_data
        )
    )
    symbol_names = (
        research_config.build_universe(
            config_data
        )
    )

    print(
        f"研究対象銘柄数: "
        f"{len(symbol_names)}"
    )
    pair_count = (
        len(symbol_names)
        * (len(symbol_names) - 1)
        // 2
    )
    print(
        f"組み合わせ数  : {pair_count:,}"
    )

    price_data = load_price_data(
        symbol_names,
        data_folder,
    )
    rows = research_pairs(
        symbol_names,
        price_data,
        research_config,
    )

    result_df = pd.DataFrame(rows)
    result_df = sort_results(result_df)

    output_path = (
        save_dir / OUTPUT_FILE_NAME
    )
    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        float_format="%.9f",
    )

    print_summary(
        result_df,
        research_config,
    )
    print(
        f"\n出力: {output_path}"
    )

    end_time = datetime.datetime.now()
    print(
        f"総実行時間: "
        f"{end_time - start_time}"
    )
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "銘柄ペアの相関・共和分・"
            "平均回帰性を研究する。"
        )
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="config.toml のパス",
    )
    parser.add_argument(
        "--data-folder",
        default=None,
        help="価格CSVのルートフォルダ",
    )
    parser.add_argument(
        "--save-dir",
        default=None,
        help="pair_research.csv の出力先",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    run(
        config_path=args.config_path,
        data_folder=args.data_folder,
        save_dir=args.save_dir,
    )


if __name__ == "__main__":
    main()
