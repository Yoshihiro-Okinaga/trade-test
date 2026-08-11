import sys
import os
import datetime
import tomllib
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import backtest
import market_data
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
    if sys.platform == "darwin":  # Macの場合
        # Macのホームディレクトリ直下のDropboxを指定
        save_dir = Path.home() / "Dropbox" / "Private" / "trade_test_results"
        save_dir.mkdir(parents=True, exist_ok=True)  # フォルダがなければ作成
    else:  # Windowsなどの場合
        #save_dir = Path("./")
        save_dir = Path("../TestResult")

    RANKING_OUTPUT_FILE = save_dir / "trade_ranking.csv"
    RANKING_OUTPUT_FILE_FULL = save_dir / "trade_ranking_full.csv"

    tasks = [
        (ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, hold_days, start_days, sma_period)
        for ref_name, target_name in config.iter_ref_target()
        for signal_type in config.signal_type_list
        for counter_trade in config.counter_trade
        for use_excess_return in config.use_excess_return
        # 閾値は指標ごとにスケールが違うので、指標ごとの候補リストを展開する
        for threshold_width in config.widths_of(signal_type)
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]

    ranking_results = []
    total_tasks = len(tasks)

    # 指標はタスクごとに計算し直すと同じ計算を何万回も繰り返すことになる。
    # 必要な組み合わせは銘柄×パラメータのぶんだけなので、先にまとめて作る。
    print("指標を事前計算しています...", flush=True)
    ref_cache, target_cache = market_data.build_caches(config)
    print(f"事前計算 完了（ref {len(ref_cache)} 件 / target {len(target_cache)} 件）")

    if config.use_process_pool:
        # config と指標キャッシュは initializer で各ワーカーに1回だけ渡す。
        # タスクごとに送ると転送だけで時間を食ってしまう。
        # map(chunksize=...) でまとめて送り、往復回数も減らす。
        chunksize = max(1, total_tasks // (MAX_WORKERS * 8))
        with ProcessPoolExecutor(
            max_workers=MAX_WORKERS,
            initializer=backtest.init_worker,
            initargs=(config, ref_cache, target_cache),
        ) as executor:
            for completed_count, result in enumerate(
                executor.map(backtest.run_one_shared, tasks, chunksize=chunksize),
                start=1,
            ):
                if result is not None:
                    ranking_results.append(result)

                print(f"\rタスク完了: {completed_count}/{total_tasks}", end="", flush=True)

    else:
        # 逐次実行でも、ワーカーと同じ場所にキャッシュを置いてから回す。
        backtest.init_worker(config, ref_cache, target_cache)
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
         "threshold_width", "hold_days", "start_days", "sma_period"],
        ascending=[False, True, True, True, True, True, True, True, True, True],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    df_ranking.insert(0, "rank", df_ranking.index + 1)
    df_ranking = format_param_columns(df_ranking)

    MAX_MAIN_ROWS = 10000
    csv_opts = dict(index=False, encoding="utf-8", float_format=f"%.{ROUND_DIGITS}f", lineterminator="\r\n")
    is_large = len(df_ranking) > MAX_MAIN_ROWS
    main_frame = df_ranking.head(MAX_MAIN_ROWS) if is_large else df_ranking
    main_frame.to_csv(RANKING_OUTPUT_FILE, **csv_opts)
    if is_large:
        df_ranking.to_csv(RANKING_OUTPUT_FILE_FULL, **csv_opts)

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
