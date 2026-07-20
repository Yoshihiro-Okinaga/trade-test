import sys
import os
import datetime
import tomllib
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import backtest
import backtest_config

MAX_WORKERS = min(32, os.cpu_count() or 1)  # 並列プロセス数
ROUND_DIGITS = 9                            # 小数点以下の桁数（四捨五入）

def main():
    start_time = datetime.datetime.now()
    print(f"ワーカー数: {MAX_WORKERS}")

    try:
        with open(Path(__file__).parent / "config.toml", "rb") as f:
            config_data = tomllib.load(f)
    except FileNotFoundError:
        print(f"エラー: {Path(__file__).parent / 'config.toml'} が見つかりません。")
        sys.exit(1)

    config = backtest_config.BackTestConfig(config_data)
    RANKING_OUTPUT_FILE = "trade_ranking_counter.csv" if config.counter_trade else "trade_ranking.csv"

    tasks = [
        (ref_name, target_name, signal_type, ref_lag_days, hold_days, start_days, sma_period)
        for ref_name in config.ref_list
        for target_name in config.target_list
        for signal_type in config.signal_type_list
        for ref_lag_days in config.ref_lag_days_list
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]

    ranking_results = []

    if config.use_process_pool:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(backtest.run_one, config, task) for task in tasks]

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    ranking_results.append(result)
    else:
        for task in tasks:
            result = backtest.run_one(config, task)
            if result is not None:
                ranking_results.append(result)

    df_ranking = pd.DataFrame(ranking_results)
    # correlation の絶対値で降順に並べる。ただし絶対値が同値の行の順序が
    # 実行ごとにブレると、出力の diff 比較（テストのゴールデン照合）が壊れる。
    # そこで target/ref/signal_type をタイブレークに使い、安定ソートで
    # 行順を完全に決定的にする。
    df_ranking["_abs_corr"] = df_ranking["correlation"].abs()
    df_ranking = df_ranking.sort_values(
        ["_abs_corr", "target", "ref", "signal_type"],
        ascending=[False, True, True, True],
        kind="mergesort",
    ).drop(columns="_abs_corr").reset_index(drop=True)
    df_ranking.insert(0, "rank", df_ranking.index + 1)
    df_ranking.to_csv(RANKING_OUTPUT_FILE, index=False, encoding="utf-8", float_format=f"%.{ROUND_DIGITS}f",)

    print("\n=== 総合ランキング ===")
    with pd.option_context("display.precision", ROUND_DIGITS,
                           "display.max_rows", None,
                           "display.width", None):
        print(df_ranking)
    print(f"\nランキング出力: {RANKING_OUTPUT_FILE}")

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"実験開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"実験終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"総実行時間: {duration}")



if __name__ == "__main__":
    main()
