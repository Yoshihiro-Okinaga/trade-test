import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROUND_DIGITS = 9

# final OOSまで到達した研究候補の凍結監査値。
# 数値を変更する場合は、対応する元CSVと同時に更新する。
#
# source_files は、この値を採った主な研究出力。
AUDIT_ROWS = [
    {
        "candidate": "Utility 50/50 Pair Portfolio",
        "study_family": "pair",
        "source_files": (
            "pair_strategy_portfolio_summary.csv / "
            "pair_strategy_final_oos_portfolio_summary.csv"
        ),
        "selection_basis": (
            "pair discovery + fixed 50/50 sleeves"
        ),
        "is_trade_count": np.nan,
        "is_average_pct": np.nan,
        "is_t_value": np.nan,
        "development_trade_count": 40,
        "development_average_pct": 0.201373,
        "development_median_pct": 0.453248,
        "development_win_rate": 67.5,
        "development_t_value": 1.155852,
        "development_stress_average_pct": 0.080130,
        "development_terminal_return_pct": 7.977779,
        "final_trade_count": 41,
        "final_average_pct": -0.086358,
        "final_median_pct": 0.107202,
        "final_win_rate": 51.219512,
        "final_t_value": -0.466981,
        "final_stress_average_pct": -0.206333,
        "final_terminal_return_pct": -3.810921,
        "development_regime_contrast_pp": np.nan,
        "final_regime_contrast_pp": np.nan,
        "mechanical_verdict": "FAIL",
        "research_verdict": "FAIL",
        "failure_mode": (
            "development positive; final baseline/stress "
            "and terminal negative"
        ),
        "current_status": "eliminated",
    },
    {
        "candidate": "OIL_USD <- COPPER_USD",
        "study_family": "predictive",
        "source_files": (
            "oil_copper_selected_strategy.csv / "
            "oil_copper_strategy_summary.csv / "
            "oil_copper_final_oos_*.csv"
        ),
        "selection_basis": (
            "best 2001-2015 t-value representative StrategyTask"
        ),
        "is_trade_count": 207,
        "is_average_pct": 1.897099980,
        "is_t_value": 2.901197831,
        "development_trade_count": 77,
        "development_average_pct": 1.016430,
        "development_median_pct": 3.691046,
        "development_win_rate": 58.441558,
        "development_t_value": 0.672402,
        "development_stress_average_pct": np.nan,
        "development_terminal_return_pct": np.nan,
        "final_trade_count": 77,
        "final_average_pct": 0.225064,
        "final_median_pct": 0.114980,
        "final_win_rate": 50.649351,
        "final_t_value": 0.260665,
        "final_stress_average_pct": -0.274936,
        "final_terminal_return_pct": np.nan,
        "development_regime_contrast_pp": np.nan,
        "final_regime_contrast_pp": np.nan,
        "mechanical_verdict": "WEAK_PASS",
        "research_verdict": "B- / skip",
        "failure_mode": (
            "edge compression; stress average negative"
        ),
        "current_status": "observe only",
    },
    {
        "candidate": "OIL_USD <- GOLD_USD x OIL down",
        "study_family": "regime",
        "source_files": (
            "oil_gold_regime_strategy_summary.csv / "
            "oil_gold_regime_final_oos_*.csv"
        ),
        "selection_basis": (
            "fixed representative strategy + pre-final down regime"
        ),
        "is_trade_count": 192,
        "is_average_pct": 2.056712460,
        "is_t_value": 2.977243195,
        "development_trade_count": 31,
        "development_average_pct": 5.154607,
        "development_median_pct": 5.874969,
        "development_win_rate": 70.967742,
        "development_t_value": 1.733071,
        "development_stress_average_pct": 4.654607,
        "development_terminal_return_pct": np.nan,
        "final_trade_count": 36,
        "final_average_pct": 0.029121,
        "final_median_pct": 0.324191,
        "final_win_rate": 52.777778,
        "final_t_value": 0.027032,
        "final_stress_average_pct": -0.470879,
        "final_terminal_return_pct": np.nan,
        "development_regime_contrast_pp": 5.695939,
        "final_regime_contrast_pp": 0.570541,
        "mechanical_verdict": "WEAK_PASS",
        "research_verdict": "B- / regime-only survival",
        "failure_mode": (
            "absolute edge collapsed; down>up contrast survived"
        ),
        "current_status": "feature idea only",
    },
    {
        "candidate": "AUD_JPY <- EUR_GBP x AUD_JPY up",
        "study_family": "regime",
        "source_files": (
            "aud_jpy_eur_gbp_regime_strategy_summary.csv / "
            "aud_jpy_regime_final_oos_*.csv"
        ),
        "selection_basis": (
            "fixed representative strategy + pre-final up regime"
        ),
        "is_trade_count": 172,
        "is_average_pct": 0.908856306,
        "is_t_value": 2.715070972,
        "development_trade_count": 22,
        "development_average_pct": 0.766379,
        "development_median_pct": 0.923636,
        "development_win_rate": 72.727273,
        "development_t_value": 1.713258,
        "development_stress_average_pct": 0.266379,
        "development_terminal_return_pct": np.nan,
        "final_trade_count": 18,
        "final_average_pct": 0.134333,
        "final_median_pct": -0.286681,
        "final_win_rate": 50.0,
        "final_t_value": 0.212011,
        "final_stress_average_pct": -0.365667,
        "final_terminal_return_pct": np.nan,
        "development_regime_contrast_pp": 0.423881,
        "final_regime_contrast_pp": -0.615853,
        "mechanical_verdict": "WEAK_PASS",
        "research_verdict": "FAIL",
        "failure_mode": "regime contrast reversed in final OOS",
        "current_status": "eliminated",
    },
    {
        "candidate": "OIL_USD <- SILVER_USD x OIL down",
        "study_family": "regime",
        "source_files": (
            "oil_silver_regime_strategy_summary.csv / "
            "oil_silver_regime_final_oos_*.csv"
        ),
        "selection_basis": (
            "fixed representative strategy + pre-final down regime"
        ),
        "is_trade_count": 224,
        "is_average_pct": 1.541670408,
        "is_t_value": 2.386478129,
        "development_trade_count": 36,
        "development_average_pct": 0.867315,
        "development_median_pct": 2.330663,
        "development_win_rate": 58.333333,
        "development_t_value": 0.355072,
        "development_stress_average_pct": 0.367315,
        "development_terminal_return_pct": np.nan,
        "final_trade_count": 45,
        "final_average_pct": -0.901510,
        "final_median_pct": -0.445705,
        "final_win_rate": 44.444444,
        "final_t_value": -1.042586,
        "final_stress_average_pct": -1.401510,
        "final_terminal_return_pct": np.nan,
        "development_regime_contrast_pp": 0.747174,
        "final_regime_contrast_pp": -1.670283,
        "mechanical_verdict": "FAIL",
        "research_verdict": "FAIL",
        "failure_mode": (
            "absolute edge negative and regime contrast reversed"
        ),
        "current_status": "eliminated",
    },
    {
        "candidate": "COPPER_USD / OIL_USD 2.5sigma Pair",
        "study_family": "pair",
        "source_files": (
            "copper_oil_pair_strategy_portfolio_summary.csv / "
            "copper_oil_pair_final_oos_*.csv"
        ),
        "selection_basis": (
            "pre-existing 2.5sigma extreme-divergence hypothesis"
        ),
        "is_trade_count": np.nan,
        "is_average_pct": np.nan,
        "is_t_value": np.nan,
        "development_trade_count": 12,
        "development_average_pct": 1.808053,
        "development_median_pct": 1.751029,
        "development_win_rate": 75.0,
        "development_t_value": 1.125061,
        "development_stress_average_pct": 1.568202,
        "development_terminal_return_pct": 21.932715,
        "final_trade_count": 15,
        "final_average_pct": 0.717076,
        "final_median_pct": -0.798310,
        "final_win_rate": 46.666667,
        "final_t_value": 0.509026,
        "final_stress_average_pct": 0.471048,
        "final_terminal_return_pct": 9.067933,
        "development_regime_contrast_pp": np.nan,
        "final_regime_contrast_pp": np.nan,
        "mechanical_verdict": "WEAK_PASS",
        "research_verdict": "B / observe",
        "failure_mode": (
            "stress survived; median/win weak; rare-win dependence"
        ),
        "current_status": "paper/forward candidate",
    },
]


def build_audit() -> pd.DataFrame:
    frame = pd.DataFrame(AUDIT_ROWS)

    frame[
        "development_to_final_retention_pct"
    ] = np.where(
        frame["development_average_pct"].abs() > 1e-12,
        (
            frame["final_average_pct"]
            / frame["development_average_pct"]
            * 100.0
        ),
        np.nan,
    )

    frame[
        "final_minus_development_pp"
    ] = (
        frame["final_average_pct"]
        - frame["development_average_pct"]
    )

    frame[
        "final_baseline_average_positive"
    ] = frame["final_average_pct"] > 0

    frame[
        "final_stress_average_positive"
    ] = frame["final_stress_average_pct"] > 0

    frame[
        "regime_relationship_survived"
    ] = np.where(
        frame["study_family"] == "regime",
        np.sign(
            frame["development_regime_contrast_pp"]
        )
        == np.sign(
            frame["final_regime_contrast_pp"]
        ),
        np.nan,
    )

    return frame


def build_summary(
    audit: pd.DataFrame,
) -> pd.DataFrame:
    regime = audit[
        audit["study_family"] == "regime"
    ]

    survived = int(
        regime[
            "regime_relationship_survived"
        ].fillna(False).sum()
    )

    return pd.DataFrame([
        {
            "metric": "finalized_hypothesis_count",
            "value": len(audit),
            "interpretation": (
                "final OOSまで到達した監査対象数"
            ),
        },
        {
            "metric": "strong_or_deployable_pass_count",
            "value": 0,
            "interpretation": (
                "現時点で本番投入可とした案は0"
            ),
        },
        {
            "metric": "final_baseline_average_positive_count",
            "value": int(
                (
                    audit["final_average_pct"] > 0
                ).sum()
            ),
            "interpretation": (
                "final平均だけならプラスの案もある"
            ),
        },
        {
            "metric": "final_stress_average_positive_count",
            "value": int(
                (
                    audit[
                        "final_stress_average_pct"
                    ] > 0
                ).sum()
            ),
            "interpretation": (
                "stress後まで平均プラスの案は少ない"
            ),
        },
        {
            "metric": (
                "median_development_to_final_retention_pct"
            ),
            "value": float(
                audit[
                    "development_to_final_retention_pct"
                ].median()
            ),
            "interpretation": (
                "study family混在の記述統計。"
                "新スコア学習には使わない"
            ),
        },
        {
            "metric": "regime_hypothesis_count",
            "value": len(regime),
            "interpretation": (
                "finalまで検証したRegime仮説数"
            ),
        },
        {
            "metric": "regime_relationship_survived_count",
            "value": survived,
            "interpretation": (
                "優位方向がfinalでも残った数"
            ),
        },
        {
            "metric": "regime_relationship_reversed_count",
            "value": len(regime) - survived,
            "interpretation": (
                "優位方向がfinalで逆転した数"
            ),
        },
    ])


def run(
    save_dir: Path,
):
    audit = build_audit()
    summary = build_summary(
        audit
    )

    save_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit_path = (
        save_dir
        / "research_method_audit_candidates.csv"
    )
    summary_path = (
        save_dir
        / "research_method_audit_summary.csv"
    )

    options = dict(
        index=False,
        encoding="utf-8",
        float_format=f"%.{ROUND_DIGITS}f",
        lineterminator="\r\n",
    )

    audit.to_csv(
        audit_path,
        **options,
    )
    summary.to_csv(
        summary_path,
        **options,
    )

    print("=== Research Method Audit Step 1 ===")
    print(
        audit[
            [
                "candidate",
                "study_family",
                "development_average_pct",
                "final_average_pct",
                "final_stress_average_pct",
                "development_to_final_retention_pct",
                "research_verdict",
            ]
        ].to_string(index=False)
    )
    print()
    print(summary.to_string(index=False))

    return audit_path, summary_path


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "final OOSまで到達した研究候補を横並びにし、"
            "edge縮小と失敗パターンを監査する。"
        )
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=Path("./"),
        help="監査CSVの出力先",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        save_dir=args.save_dir,
    )
