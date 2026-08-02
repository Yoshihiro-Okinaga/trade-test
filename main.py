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

# パラメータ列は成績列と違い、9桁も要らない（1.000000000 は読みにくい）。
# かといって一律に整数化もできない（0.5 刻みなら 0.5 / 1.0、
# 0.01 刻みなら 1.00 と出したい）。そこで列に実際に現れる値から
# 必要な小数桁数を求め、その桁で揃えて文字列にしておく。
# 文字列にすると to_csv の float_format の対象外になるため、
# 成績列の 9 桁指定はそのまま保たれる。
PARAM_COLUMNS = ["threshold_width"]


def _decimals_needed(values, limit=6):
    """値をすべて表現するのに必要な小数桁数を返す。"""
    needed = 0
    for value in values:
        if pd.isna(value):
            continue
        for digits in range(limit + 1):
            if round(float(value), digits) == float(value):
                needed = max(needed, digits)
                break
        else:
            needed = limit
    return needed


def format_param_columns(df):
    """パラメータ列を、値に見合った桁数の文字列に変換する。"""
    for column in PARAM_COLUMNS:
        if column not in df.columns:
            continue
        digits = _decimals_needed(df[column])
        df[column] = df[column].map(
            lambda v: "" if pd.isna(v) else f"{float(v):.{digits}f}"
        )
    return df

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
    RANKING_OUTPUT_FILE = "trade_ranking.csv"

    tasks = [
        (ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, ref_lag_days, hold_days, start_days, sma_period)
        for ref_name in config.ref_list
        for target_name in config.target_list
        for signal_type in config.signal_type_list
        for counter_trade in config.counter_trade
        for use_excess_return in config.use_excess_return
        # 閾値は指標ごとにスケールが違うので、指標ごとの候補リストを展開する
        for threshold_width in config.widths_of(signal_type)
        for ref_lag_days in config.ref_lag_days_list
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]

    ranking_results = []
    total_tasks = len(tasks)

    if config.use_process_pool:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(backtest.run_one, config, task)
                for task in tasks
            ]

            for completed_count, future in enumerate(
                as_completed(futures),
                start=1,
            ):
                result = future.result()

                if result is not None:
                    ranking_results.append(result)

                print(f"\rタスク完了: {completed_count}/{total_tasks}", end="", flush=True)

    else:
        for completed_count, task in enumerate(tasks, start=1):
            result = backtest.run_one(config, task)

            if result is not None:
                ranking_results.append(result)

            print(f"\rタスク完了: {completed_count}/{total_tasks}", end="", flush=True)

    df_ranking = pd.DataFrame(ranking_results)
    # t値の降順に並べる。t値は「平均損益がノイズと区別できるか」を測るので、
    # 平均が大きいだけの見かけ倒し（少数サンプル、σが巨大）を下位に沈められる。
    # 相関と違い符号に意味がある（プラスが良い）ため、絶対値は取らない。
    # 同値の行の順序が実行ごとにブレると出力の diff 比較が壊れるので、
    # 全パラメータをタイブレークに使い、安定ソートで行順を決定的にする。
    df_ranking = df_ranking.sort_values(
        ["t_value", "target", "ref", "signal_type", "counter_trade", "use_excess_return",
         "threshold_width", "ref_lag_days", "hold_days", "start_days", "sma_period"],
        ascending=[False, True, True, True, True, True, True, True, True, True, True],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    df_ranking.insert(0, "rank", df_ranking.index + 1)
    df_ranking = format_param_columns(df_ranking)
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
