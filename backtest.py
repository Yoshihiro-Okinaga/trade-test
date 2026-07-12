import pandas as pd
from pathlib import Path

# === 設定 ===
REF_LIST = [
    "US30_Futures",
    "CBOE_Volatility_Index",
    "COPPER_USD",
    "GOLD_USD",
    "SILVER_USD",
    "PLATINUM_USD",
    "JAPAN255_Futures",
    "USSPX500_Futures",
    "UK100_Futures",
    "NQ100_Futures",
]

TARGET_LIST = [
    "US30_Futures",
    "CBOE_Volatility_Index",
    "COPPER_USD",
    "GOLD_USD",
    "SILVER_USD",
    "PLATINUM_USD",
    "JAPAN255_Futures",
    "USSPX500_Futures",
    "UK100_Futures",
    "NQ100_Futures",
]

LAG_DAYS = 3          # 何日前と比較するか
RISE_PERCENT = 2.0    # 何％上昇したら買うか（例：2%）
HOLD_DAYS = 2         # 仕掛け日の何取引日後に決済するか
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


def calc_trade_results(ref_name, target_name):
    if LAG_DAYS < 1:
        raise ValueError("LAG_DAYSは1以上を指定してください。")
    if HOLD_DAYS < 1:
        raise ValueError("HOLD_DAYSは1以上を指定してください。")

    ref = load_data(ref_name)
    target = load_data(target_name)

    # === Ref の騰落率（何日前比）を計算 ===
    ref["ref_shift"] = ref["終値"].shift(LAG_DAYS)
    ref["ref_change_pct"] = (ref["終値"] - ref["ref_shift"]) / ref["ref_shift"] * 100

    # === 日付で結合（inner join）===
    merged = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))

    # Refの終値確定後、次の取引日にTargetを仕掛ける
    merged["ref_change_pct_signal"] = merged["ref_change_pct"].shift(1)
    merged["ref_trigger_close"] = merged["終値_Ref"].shift(1)

    # === 売買シミュレーション ===
    results = []
    debug_results = []

    position = None  # None or "LONG"
    entry_price = None
    actual_entry_date = None
    trigger_ref_close = None
    entry_idx = None

    for idx, row in merged.iterrows():
        date = row["日付"]
        target_close = row["終値_Target"]
        ref_change = row["ref_change_pct_signal"]

        # --- 買い条件 ---
        if position is None:
            if ref_change >= RISE_PERCENT:
                position = "LONG"
                entry_price = target_close
                actual_entry_date = date
                trigger_ref_close = row["ref_trigger_close"]
                entry_idx = idx

        # --- 決済条件（設定した取引日数後の終値で決済）---
        else:
            if idx - entry_idx >= HOLD_DAYS:
                exit_price = target_close
                profit = exit_price - entry_price
                profit_pct = profit / entry_price * 100

                results.append({
                    "entry_date": actual_entry_date,
                    "exit_date": date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "profit": profit,
                    "profit_pct": profit_pct,
                    "year": actual_entry_date.year
                })

                debug_results.append({
                    "entry_date": actual_entry_date,
                    "exit_date": date,
                    "trigger_ref_close": trigger_ref_close,
                    "target_entry_price": entry_price,
                    "target_exit_price": exit_price
                })

                position = None
                entry_price = None
                actual_entry_date = None
                trigger_ref_close = None
                entry_idx = None

    # === デバッグ出力 ===
    #df_debug = pd.DataFrame(debug_results)
    #output_file = f"{DEBUG_OUTPUT_FILE}_{ref_name}_{target_name}.csv"
    #df_debug.to_csv(output_file, index=False, encoding="utf-8")

    # === 年ごとに集計 ===
    df_results = pd.DataFrame(results)

    if df_results.empty:
        year_summary = pd.DataFrame(columns=["year", "profit"])
    else:
        year_summary = df_results.groupby("year")["profit"].sum().reset_index()

    print(f"\n=== {ref_name} → {target_name} ===")
    print("=== 年間損益 ===")
    print(year_summary)

    print("\n=== 全取引一覧 ===")
    print(df_results)

    #print(f"\nデバッグ出力: {output_file}")

    return df_results


def main():
    ranking_results = []

    for ref_name in REF_LIST:
        for target_name in TARGET_LIST:
            df_results = calc_trade_results(ref_name, target_name)

            trade_count = len(df_results)

            if trade_count == 0:
                total_profit = 0.0
                return_pct_sum = 0.0
                win_rate = 0.0
            else:
                total_profit = df_results["profit"].sum()
                return_pct_sum = df_results["profit_pct"].sum()
                win_rate = (df_results["profit"] > 0).mean() * 100

            ranking_results.append({
                "ref": ref_name,
                "target": target_name,
                "trade_count": trade_count,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "return_pct_sum": return_pct_sum
            })

    df_ranking = pd.DataFrame(ranking_results)
    df_ranking = df_ranking.sort_values(
        "return_pct_sum",
        ascending=False
    ).reset_index(drop=True)
    df_ranking.insert(0, "rank", df_ranking.index + 1)
    df_ranking.to_csv(RANKING_OUTPUT_FILE, index=False, encoding="utf-8")

    print("\n=== 総合ランキング ===")
    print(df_ranking)
    print(f"\nランキング出力: {RANKING_OUTPUT_FILE}")


if __name__ == "__main__":
    main()