import argparse
from pathlib import Path

import numpy as np
import pandas as pd


TARGETS = [
    ("OIL_USD", "COPPER_USD"),
    ("OIL_USD", "GOLD_USD"),
    ("AUD_JPY", "EUR_GBP"),
    ("OIL_USD", "SILVER_USD"),
]

FINAL_MAP = {
    ("OIL_USD", "COPPER_USD"):
        "OIL_USD <- COPPER_USD",
    ("OIL_USD", "GOLD_USD"):
        "OIL_USD <- GOLD_USD x OIL down",
    ("AUD_JPY", "EUR_GBP"):
        "AUD_JPY <- EUR_GBP x AUD_JPY up",
    ("OIL_USD", "SILVER_USD"):
        "OIL_USD <- SILVER_USD x OIL down",
}


def run(
    plateau_path: Path,
    final_audit_path: Path,
    output_path: Path,
):
    plateau = pd.read_csv(
        plateau_path
    )
    final = pd.read_csv(
        final_audit_path
    )

    selected = pd.DataFrame(
        TARGETS,
        columns=["target", "ref"],
    ).merge(
        plateau,
        on=["target", "ref"],
        how="left",
        validate="one_to_one",
    )

    selected["audit_candidate"] = [
        FINAL_MAP[
            (row.target, row.ref)
        ]
        for row in selected.itertuples()
    ]

    selected = selected.merge(
        final[
            [
                "candidate",
                "research_verdict",
                "failure_mode",
                "current_status",
            ]
        ],
        left_on="audit_candidate",
        right_on="candidate",
        how="left",
        validate="one_to_one",
    )

    selected["rule_a_pass"] = (
        selected["t_value_is"]
        >= 2.0
    )

    selected["rule_b_pass"] = (
        (
            selected["t_value_is"]
            >= 2.0
        )
        & (
            selected[
                "neighbor_worst_t"
            ]
            >= 1.0
        )
    )

    selected.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        float_format="%.9f",
        lineterminator="\r\n",
    )

    print(
        f"output: {output_path}"
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plateau",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--final-audit",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "parameter_plateau_step3_audit.csv"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        plateau_path=args.plateau,
        final_audit_path=args.final_audit,
        output_path=args.output,
    )
