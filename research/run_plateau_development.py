import argparse
import sys
from pathlib import Path


RESEARCH_DIR = Path(
    __file__
).resolve().parent
PROJECT_DIR = RESEARCH_DIR.parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_DIR),
    )

import strategy_screening


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Parameter Plateau用の"
            "2016-2020 development rankingを"
            "別フォルダへ出力する。"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            PROJECT_DIR
            / "config_plateau_development.toml"
        ),
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=(
            PROJECT_DIR
            / "plateau_development_results"
        ),
    )
    parser.add_argument(
        "--data-folder",
        type=Path,
        default=None,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    strategy_screening.main(
        config_path=args.config,
        data_folder=args.data_folder,
        save_dir=args.save_dir,
    )
