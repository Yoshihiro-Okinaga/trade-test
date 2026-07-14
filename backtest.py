import pandas as pd
import operator
import os
import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# === 設定 ===
REF_LIST = [
    "CBOE_Volatility_Index",
    "DAX_Futures",
    "EUR_GBP",
    "EUR_USD",
    "GBP_USD",
    "GOLD_USD",
    "JAPAN255_Futures",
    "NQ100_Futures",
    "OIL_USD",
    "UK100_Futures",
    "US30_Futures",
    "USD_JPY",
    "USSPX500_Futures",
    "AUD_JPY",
    "AUD_USD",
    "CAD_JPY",
    "CHF_JPY",
    "COPPER_USD",
    "EUR_AUD",
    "EUR_CHF",
    "EUR_JPY",
    "EUR_NZD",
    "GBP_AUD",
    "GBP_CHF",
    "GBP_JPY",
    "NZD_JPY",
    "NZD_USD",
    "PLATINUM_USD",
    "SILVER_USD",
    "TRY_JPY",
    "USD_CAD",
    "USD_CHF",
    "ZAR_JPY",
]

TARGET_LIST = {
    "US30_Futures": 4.0,
    #"COPPER_USD": 0.02,
    "GOLD_USD": 1.0,
    #"SILVER_USD": 0.1,
    #"PLATINUM_USD": 5.0,
    "JAPAN255_Futures": 10,
    "USSPX500_Futures": 2.0,
    "UK100_Futures": 3.0,
    "NQ100_Futures": 0.5,
}

REF_LAG_DAYS_LIST = range(3, 8)        # 何日前と比較するか
RISE_PERCENT = 1.0                     # 何％上昇したら買うか（例：2%）
HOLD_DAYS_LIST = range(3, 8)           # 仕掛け日の何取引日後に決済するか
START_DAYS_LIST = range(1, 4)          # シグナルが出た何日後に仕掛けるか
MIN_TRADE_COUNT = 200                  # 取引回数がこの値未満の場合はランキングに含めない
MAX_WORKERS = min(32, os.cpu_count())  # 並列プロセス数
DEBUG_OUTPUT_FILE = "trade_debug"
RANKING_OUTPUT_FILE = "trade_ranking.csv"


# === データ読み込み ===
def load_data(path):
    folder = Path("./stock-data/")   # 探したいフォルダ

    files = list(folder.rglob(f"{path}.csv"))

    if not files:
        raise FileNotFoundError(f"{path} が見つかりませんでした")

    df = pd.read_csv(files[0])
    df = df.dropna()
    df["日付"] = pd.to_datetime(df["日付"])
    df = df.sort_values("日付")
    return df


def calc_trade_results(ref_name, target_name, ref_lag_days, hold_days, start_days):
    if ref_lag_days < 1:
        raise ValueError("ref_lag_daysは1以上を指定してください。")
    if hold_days < 1:
        raise ValueError("hold_daysは1以上を指定してください。")
    if start_days < 1:
        raise ValueError("start_daysは1以上を指定してください。")

    ref = load_data(ref_name)
    target = load_data(target_name)

    # === Ref の騰落率（何日前比）を計算 ===
    ref["ref_shift"] = ref["終値"].shift(ref_lag_days)
    ref["ref_change_pct"] = (ref["終値"] - ref["ref_shift"]) / ref["ref_shift"] * 100
    ref["ref_change_pct_signal"] = ref["ref_change_pct"].shift(start_days)
    ref["ref_trigger_close"] = ref["終値"].shift(start_days)

    target["target_exit"] = target["終値"].shift(-hold_days)
    target["exit_date"] = target["日付"].shift(-hold_days)
    target["target_change"] = target["target_exit"] - target["終値"]
    target["target_change_pct"] = target["target_change"] / target["終値"] * 100

    # === 日付で結合（inner join）===
    merged = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))

    # Refの終値確定後、次の取引日にTargetを仕掛ける


    # === 売買シミュレーション ===
    results = []

    TRADE_COST = TARGET_LIST[target_name]
    POS_NAME = ["long", "short"]
    POS_RATE = [1, -1]
    OPERATORS = [operator.gt, operator.lt]

    # iterrows は行ごとに Series を生成して遅いため、列を先に取り出しておく
    dates = merged["日付"].to_list()                            # Timestamp のまま保持
    exit_dates = merged["exit_date"].to_list()                    # Timestamp のまま保持
    target_closes = merged["終値_Target"].to_numpy()
    ref_change_pcts = merged["ref_change_pct_signal"].to_numpy()
    ref_triggers = merged["ref_trigger_close"].to_numpy()
    target_shifts = merged["target_exit"].to_numpy()
    target_changes = merged["target_change"].to_numpy()

    for idx in range(len(merged)):
        date = dates[idx]
        target_close = target_closes[idx]
        ref_change_pct = ref_change_pcts[idx]
        profit_ls = [None, None]
        profit_ls_pct = [None, None]

        for i in range(2):
            if not OPERATORS[i](ref_change_pct, POS_RATE[i] * RISE_PERCENT):
                continue

            entry_price = target_close
            trigger_ref_close = ref_triggers[idx]
            exit_price = target_shifts[idx]

            if pd.isna(exit_price):
                continue

            exit_date = exit_dates[idx]
            profit = POS_RATE[i] * target_changes[idx] - TRADE_COST
            profit_pct = profit / entry_price * 100
            profit_ls[i] = profit
            profit_ls_pct[i] = profit_pct

            results.append({
                "position": POS_NAME[i],
                "entry_date": date,
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "trigger_ref_close": trigger_ref_close,
                "profit": profit,
                "profit_pct": profit_pct,
                "profit_long": profit_ls[0],
                "profit_long_pct": profit_ls_pct[0],
                "profit_short": profit_ls[1],
                "profit_short_pct": profit_ls_pct[1],
                "year": date.year
            })

    # === 年ごとに集計 ===
    df_results = pd.DataFrame(results)

    if df_results.empty:
        year_summary = pd.DataFrame(columns=["year", "profit"])
    else:
        year_summary = df_results.groupby("year")["profit"].sum().reset_index()

    df_results.attrs["year_summary"] = year_summary
    corr = merged["target_change_pct"].corr(merged["ref_change_pct_signal"])
    df_results.attrs["correlation"] = corr

    return df_results


def run_one(task):
    """ワーカープロセスで実行される単位。集計まで済ませて軽い dict だけ返す。"""
    ref_name, target_name, ref_lag_days, hold_days, start_days = task

    df_results = calc_trade_results(ref_name, target_name, ref_lag_days, hold_days, start_days)

    trade_count = len(df_results)
    if trade_count < MIN_TRADE_COUNT:
        return None

    total_profit = df_results["profit"].sum()
    return_pct_sum = df_results["profit_pct"].sum()
    average_pct = df_results["profit_pct"].mean()
    average_long_pct = df_results["profit_long_pct"].mean()
    average_short_pct = df_results["profit_short_pct"].mean()
    win_rate = (df_results["profit"] > 0).mean() * 100
    year_summary = df_results.attrs["year_summary"]
    corr = df_results.attrs["correlation"]

    return {
        "target": target_name,
        "ref": ref_name,
        "ref_lag_days": ref_lag_days,
        "hold_days": hold_days,
        "start_days": start_days,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "total_profit": total_profit,
        "return_pct_sum": return_pct_sum,
        "average_pct": average_pct,
        "average_long_pct": average_long_pct,
        "average_short_pct": average_short_pct,
        "correlation": corr,
        #"year_summary": year_summary,
    }


def main():
    start_time = datetime.datetime.now()
    print(f"ワーカー数: {MAX_WORKERS}")

    tasks = [
        (ref_name, target_name, ref_lag_days, hold_days, start_days)
        for ref_name in REF_LIST
        for target_name in TARGET_LIST
        for ref_lag_days in REF_LAG_DAYS_LIST
        for hold_days in HOLD_DAYS_LIST
        for start_days in START_DAYS_LIST
    ]

    ranking_results = []

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(run_one, task) for task in tasks]

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                ranking_results.append(result)

    df_ranking = pd.DataFrame(ranking_results)
    df_ranking = df_ranking.sort_values(
        "average_pct",
        ascending=False
    ).reset_index(drop=True)
    df_ranking.insert(0, "rank", df_ranking.index + 1)
    df_ranking.to_csv(RANKING_OUTPUT_FILE, index=False, encoding="utf-8")

    print("\n=== 総合ランキング ===")
    print(df_ranking)
    print(f"\nランキング出力: {RANKING_OUTPUT_FILE}")

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"実験開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"実験終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"総実行時間: {duration}")


if __name__ == "__main__":
    main()