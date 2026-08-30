import argparse
from pathlib import Path

import pandas as pd


TARGET_FILES = (
    "9502_中部電力.csv",
    "9503_関西電力.csv",
    "9508_九州電力.csv",
)

ADJUSTED_CLOSE_CANDIDATES = (
    "調整後終値",
    "調整済終値",
    "Adj Close",
    "Adjusted Close",
    "adjusted_close",
    "adj_close",
)

DIVIDEND_CANDIDATES = (
    "配当",
    "配当金",
    "1株配当",
    "Dividend",
    "Dividends",
    "dividend",
    "dividends",
)

SPLIT_CANDIDATES = (
    "株式分割",
    "分割",
    "Stock Splits",
    "stock_splits",
)


def find_unique_csv(
    root: Path,
    file_name: str,
) -> Path:
    matches = sorted(root.rglob(file_name))

    if not matches:
        raise FileNotFoundError(
            f"{file_name} が見つかりません: {root}"
        )

    if len(matches) > 1:
        paths = "\n".join(
            f"  {path}"
            for path in matches
        )
        raise RuntimeError(
            f"{file_name} が複数見つかりました:\n"
            f"{paths}"
        )

    return matches[0]


def matching_columns(
    columns: list[str],
    candidates: tuple[str, ...],
) -> list[str]:
    lower_map = {
        str(column).strip().lower(): str(column)
        for column in columns
    }

    found = []
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lower_map:
            found.append(lower_map[key])

    return found


def inspect_header(
    csv_path: Path,
) -> dict:
    # ヘッダーだけ読む。価格や日付の行データは一切読み込まない。
    header = pd.read_csv(
        csv_path,
        nrows=0,
    )
    columns = [
        str(column)
        for column in header.columns
    ]

    return {
        "path": csv_path,
        "columns": columns,
        "adjusted_close": matching_columns(
            columns,
            ADJUSTED_CLOSE_CANDIDATES,
        ),
        "dividend": matching_columns(
            columns,
            DIVIDEND_CANDIDATES,
        ),
        "split": matching_columns(
            columns,
            SPLIT_CANDIDATES,
        ),
    }


def print_result(
    file_name: str,
    result: dict,
):
    print("=" * 72)
    print(file_name)
    print(f"Path: {result['path']}")
    print("Columns:")
    for column in result["columns"]:
        print(f"  - {column}")

    adjusted = result["adjusted_close"]
    dividend = result["dividend"]
    split = result["split"]

    print()
    print(
        "Adjusted close candidate: "
        + (
            ", ".join(adjusted)
            if adjusted
            else "なし"
        )
    )
    print(
        "Dividend candidate      : "
        + (
            ", ".join(dividend)
            if dividend
            else "なし"
        )
    )
    print(
        "Split candidate         : "
        + (
            ", ".join(split)
            if split
            else "なし"
        )
    )


def run(
    data_folder: Path,
):
    print("=== Pair Stock CSV Header Check ===")
    print(
        "行データは読まず、CSVヘッダーだけ確認します。"
    )
    print(f"Search root: {data_folder}")
    print()

    results = {}

    for file_name in TARGET_FILES:
        csv_path = find_unique_csv(
            data_folder,
            file_name,
        )
        result = inspect_header(csv_path)
        results[file_name] = result
        print_result(
            file_name,
            result,
        )
        print()

    has_adjusted_close = all(
        bool(result["adjusted_close"])
        for result in results.values()
    )
    has_dividend = all(
        bool(result["dividend"])
        for result in results.values()
    )

    print("=" * 72)
    print("Summary")
    print(
        "3銘柄すべてに調整後終値候補: "
        f"{'YES' if has_adjusted_close else 'NO'}"
    )
    print(
        "3銘柄すべてに配当候補      : "
        f"{'YES' if has_dividend else 'NO'}"
    )
    print()
    print(
        "この出力だけをChatGPTへ送ってください。"
    )
    print(
        "2021年以降の価格・日付・成績は表示しません。"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Pair本命の電力株CSVについて、"
            "2021+のデータを見ずにヘッダーだけ確認する。"
        )
    )
    parser.add_argument(
        "--data-folder",
        type=Path,
        default=Path("stock-data/Manual"),
        help=(
            "stock-data のルート。"
            "デフォルト: ./stock-data/Manual"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.data_folder)
