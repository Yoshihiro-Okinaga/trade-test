import pandas as pd

# === 設定 ===
US30_FILE = "US30_Futures.csv"
JP225_FILE = "JAPAN255_Futures.csv"

LAG_DAYS = 3          # 何日前と比較するか
RISE_PERCENT = 2.0    # 何％上昇したら買うか（例：2%）
DEBUG_OUTPUT_FILE = "trade_debug.csv"


# === データ読み込み ===
def load_data(path):
    df = pd.read_csv("./stock-data/FXCFD/" + path)
    df = df.dropna()
    df["日付"] = pd.to_datetime(df["日付"])
    df = df.sort_values("日付")  # 昇順ソート（必須）
    return df


def main():
    us = load_data(US30_FILE)
    jp = load_data(JP225_FILE)

    # === US30 の騰落率（何日前比）を計算 ===
    us["US30_shift"] = us["終値"].shift(LAG_DAYS)
    us["US30_change_pct"] = (us["終値"] - us["US30_shift"]) / us["US30_shift"] * 100

    # === 日付で結合（inner join）===
    merged = pd.merge(us, jp, on="日付", suffixes=("_US", "_JP"))

    # US30の終値確定後、次の取引日にJPを仕掛ける
    merged["US30_change_pct_signal"] = merged["US30_change_pct"].shift(1)
    merged["US30_trigger_close"] = merged["終値_US"].shift(1)

    # === 売買シミュレーション ===
    results = []
    debug_results = []

    position = None  # None or "LONG"
    entry_price = None
    actual_entry_date = None
    trigger_us30_close = None

    for idx, row in merged.iterrows():
        date = row["日付"]
        jp_close = row["終値_JP"]
        us_change = row["US30_change_pct_signal"]

        # --- 買い条件 ---
        if position is None:
            if us_change >= RISE_PERCENT:
                position = "LONG"
                entry_price = jp_close
                actual_entry_date = date
                trigger_us30_close = row["US30_trigger_close"]

        # --- 決済条件（翌日終値で決済）---
        else:
            # 翌日が存在するか確認
            if idx + 1 < len(merged):
                exit_price = merged.iloc[idx + 1]["終値_JP"]
                profit = exit_price - entry_price

                results.append({
                    "entry_date": date,
                    "exit_date": merged.iloc[idx + 1]["日付"],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "profit": profit,
                    "year": date.year
                })

                debug_results.append({
                    "entry_date": actual_entry_date,
                    "exit_date": merged.iloc[idx + 1]["日付"],
                    "trigger_us30_close": trigger_us30_close,
                    "jp_entry_price": entry_price,
                    "jp_exit_price": exit_price
                })

            position = None
            entry_price = None
            actual_entry_date = None
            trigger_us30_close = None

    # === デバッグ出力 ===
    df_debug = pd.DataFrame(debug_results)
    df_debug.to_csv(DEBUG_OUTPUT_FILE, index=False, encoding="utf-8-sig")

    # === 年ごとに集計 ===
    df_results = pd.DataFrame(results)
    year_summary = df_results.groupby("year")["profit"].sum().reset_index()

    print("=== 年間損益 ===")
    print(year_summary)

    print("\n=== 全取引一覧 ===")
    print(df_results)

    print(f"\nデバッグ出力: {DEBUG_OUTPUT_FILE}")


if __name__ == "__main__":
    main()