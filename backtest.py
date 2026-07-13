import pandas as pd
import operator
import os
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

REF_LAG_DAYS_LIST = range(3, 4)     # 何日前と比較するか
RISE_PERCENT = 1.0                  # 何％上昇したら買うか（例：2%）
HOLD_DAYS_LIST = range(3, 4)        # 仕掛け日の何取引日後に決済するか
START_DAYS_LIST = range(2, 3)       # シグナルが出た何日後に仕掛けるか
MIN_TRADE_COUNT = 200               # 取引回数がこの値未満の場合はランキングに含めない
MAX_WORKERS = os.cpu_count()        # 並列プロセス数
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

    # === 日付で結合（inner join）===
    merged = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))

    # Refの終値確定後、次の取引日にTargetを仕掛ける
    merged["ref_change_pct_signal"] = merged["ref_change_pct"].shift(start_days)
    merged["ref_trigger_close"] = merged["終値_Ref"].shift(start_days)

    # === 売買シミュレーション ===
    results = []

    TRADE_COST = TARGET_LIST[target_name]
    POS_NAME = ["Long", "Short"]
    POS_RATE = [1, -1]
    REV_POS_RATE = [-1, 1]
    OPERATORS = [operator.gt, operator.lt]

    position = [None, None]
    
    entry_price = [None, None]
    actual_entry_date = [None, None]
    trigger_ref_close = [None, None]
    entry_idx = [None, None]

    # iterrows は行ごとに Series を生成して遅いため、列を先に取り出しておく
    dates = merged["日付"].to_list()                            # Timestamp のまま保持
    target_closes = merged["終値_Target"].to_numpy()
    ref_changes = merged["ref_change_pct_signal"].to_numpy()
    ref_triggers = merged["ref_trigger_close"].to_numpy()

    for idx in range(len(merged)):
        date = dates[idx]
        target_close = target_closes[idx]
        ref_change = ref_changes[idx]

        for i in range(2):
            if position[i] is None:
                if OPERATORS[i](ref_change, POS_RATE[i] * RISE_PERCENT):
                    position[i] = POS_NAME[i]
                    entry_price[i] = target_close
                    actual_entry_date[i] = date
                    trigger_ref_close[i] = ref_triggers[idx]
                    entry_idx[i] = idx

            # --- 決済条件（設定した取引日数後の終値で決済）---
            else:
                if idx - entry_idx[i] >= hold_days:
                    exit_price = target_close
                    profit = POS_RATE[i] * (exit_price - entry_price[i]) - TRADE_COST
                    profit_pct = profit / entry_price[i] * 100
                    rev_profit = REV_POS_RATE[i] * (exit_price - entry_price[i]) - TRADE_COST
                    rev_profit_pct = rev_profit / entry_price[i] * 100

                    results.append({
                        "position": position[i],
                        "entry_date": actual_entry_date[i],
                        "exit_date": date,
                        "entry_price": entry_price[i],
                        "exit_price": exit_price,
                        "trigger_ref_close": trigger_ref_close[i],
                        "profit": profit,
                        "profit_pct": profit_pct,
                        "rev_profit": rev_profit,
                        "rev_profit_pct": rev_profit_pct,
                        "year": actual_entry_date[i].year
                    })

                    position[i] = None
                    entry_price[i] = None
                    actual_entry_date[i] = None
                    trigger_ref_close[i] = None
                    entry_idx[i] = None

    # === 年ごとに集計 ===
    df_results = pd.DataFrame(results)

    if df_results.empty:
        year_summary = pd.DataFrame(columns=["year", "profit"])
    else:
        year_summary = df_results.groupby("year")["profit"].sum().reset_index()

    print(f"\n=== {ref_name} → {target_name} ===")
    print("=== 年間損益 ===")
    print(year_summary)

    #print("\n=== 全取引一覧 ===")
    #print(df_results)

    #print(f"\nデバッグ出力: {output_file}")

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
    win_rate = (df_results["profit"] > 0).mean() * 100
    rev_average_pct = df_results["rev_profit_pct"].mean()

    return {
        "target": target_name,
        "ref": ref_name,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "total_profit": total_profit,
        "return_pct_sum": return_pct_sum,
        "average_pct": average_pct,
        "rev_average_pct": rev_average_pct,
    }


def main():
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


if __name__ == "__main__":
    main()