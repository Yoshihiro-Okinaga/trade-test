import pandas as pd
import operator
import os
import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from enum import StrEnum
from itertools import combinations

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

class SignalType(StrEnum):
    CHANGE = "change"
    SMA = "sma"
    BB = "bb"
    MACD = "macd"
    RSI = "rsi"
    DI = "di"
    ADX = "adx"
    STOCH = "stoch"

base_path = Path("./stock-data/Manual/FXCFD")
csv_files = list(base_path.rglob("*.csv"))
REF_LIST = [f.stem for f in csv_files]  # サブフォルダを含めて CSV を検索
TARGET_LIST = REF_LIST.copy()


SIGNAL_TYPE_LIST = ["change", "sma", "bb", "macd", "rsi", "di", "adx", "stoch", "Test"]
TRADE_CODE_TYPE = "all" # all, same, not_same
ROUND_DIGITS = 9                            # 小数点以下の桁数（四捨五入）
REF_LAG_DAYS_LIST = range(15, 16)           # 何日前と比較するか
RISE_PERCENT = 1.0                          # 何％上昇したら買うか（例：2%）
HOLD_DAYS_LIST = range(15, 16)              # 仕掛け日の何取引日後に決済するか
START_DAYS_LIST = range(1, 2)               # シグナルが出た何日後に仕掛けるか
SMA_PERIOD_LIST = range(10, 11)             # SMAの期間（1日移動平均は終値そのもの）
MIN_TRADE_COUNT = 10                        # 取引回数がこの値未満の場合はランキングに含めない
MAX_WORKERS = min(32, os.cpu_count() or 1)  # 並列プロセス数
COUNTER_TRADE = False
CALC_ONLY_CORRELATION = False
USE_PROCESS_POOL = True # Trueにすると、CPUコア数に応じて並列処理される。Falseにするとシングルスレッドになるが、デバッグがやりやすくなる
DEBUG_OUTPUT_FILE = "trade_debug"
RANKING_OUTPUT_FILE = "trade_ranking_counter.csv" if COUNTER_TRADE else "trade_ranking.csv"

# ワーカープロセスごとに、読み込み済みのCSVデータを保持する
DATA_CACHE = {}


# === データ読み込み ===
def load_data(path):
    if path in DATA_CACHE:
        return DATA_CACHE[path].copy()

    folder = Path("./stock-data/Manual/")   # 探したいフォルダ

    files = list(folder.rglob(f"{path}.csv"))

    if not files:
        raise FileNotFoundError(f"{path} が見つかりませんでした")

    df = pd.read_csv(files[0])
    # 他の列（出来高など）の欠損で行が消えると shift() の「何営業日前」がズレるため、
    # 実際に使う列だけを対象にする
    df = df.dropna(subset=["日付", "終値", "高値", "安値"])
    df["日付"] = pd.to_datetime(df["日付"])
    df = df.sort_values("日付")
    DATA_CACHE[path] = df

    # 計算中に列を追加するため、キャッシュ本体ではなくコピーを返す
    return DATA_CACHE[path].copy()


def calc_trade_results(ref_name, target_name, signal_type, ref_lag_days, hold_days, start_days, sma_period):
    if ref_lag_days < 1:
        raise ValueError("ref_lag_daysは1以上を指定してください。")
    if hold_days < 1:
        raise ValueError("hold_daysは1以上を指定してください。")
    if start_days < 1:
        raise ValueError("start_daysは1以上を指定してください。")

    if TRADE_CODE_TYPE == "same" and ref_name != target_name:
        return None, None
    if TRADE_CODE_TYPE == "not_same" and ref_name == target_name:
        return None, None

    ref = load_data(ref_name)
    target = load_data(target_name)

    target["target_base"] = target["終値"]
    target["target_exit"] = target["target_base"].shift(-hold_days)
    target["exit_date"] = target["日付"].shift(-hold_days)
    target["target_change"] = target["target_exit"] - target["target_base"]
    target["target_change_pct"] = target["target_change"] / target["target_base"] * 100

    # === Ref の騰落率（何日前比）を計算 ===
    ref["ref_base"] = ref["終値"]

    # change
    ref["ref_shift"] = ref["ref_base"].shift(ref_lag_days)
    change_pct = (ref["ref_base"] - ref["ref_shift"]) / ref["ref_shift"] * 100
    ref["ref_signal_change"] = change_pct.shift(start_days)

    # sma
    sma = ref["ref_base"].rolling(sma_period).mean()
    sma_pct = (ref["ref_base"] - sma) / sma * 100
    ref["ref_signal_sma"] = sma_pct.shift(start_days)

    # bb
    bb_std = ref["ref_base"].rolling(sma_period).std()
    bb = (ref["ref_base"] - sma) / bb_std   # 何σ乖離しているか（z-score）
    ref["ref_signal_bb"] = bb.shift(start_days)
    
    # macd
    ema_fast = ref["ref_base"].ewm(span=12, adjust=False).mean()
    ema_slow = ref["ref_base"].ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    ref["ref_signal_macd"] = macd.shift(start_days)

    # rsi
    delta = ref["ref_base"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(sma_period).mean()
    avg_loss = loss.rolling(sma_period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    ref["ref_signal_rsi"] = rsi.shift(start_days)

    # ADX and DI
    high = ref["高値"]
    low = ref["安値"]
    close = ref["ref_base"]
    prev_close = close.shift(1)

    # True Range
    tr = pd.concat([high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)

    # +DM / -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # 平滑化（Wilderの平滑化を簡易にrolling meanで代用）
    atr = tr.rolling(sma_period).mean()
    plus_di = 100 * plus_dm.rolling(sma_period).mean() / atr
    minus_di = 100 * minus_dm.rolling(sma_period).mean() / atr
    di_diff = plus_di - minus_di
    ref["ref_signal_di"] = di_diff.shift(start_days)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(sma_period).mean()
    ref["ref_signal_adx"] = adx.shift(start_days)

     # stoch
    low_min = ref["安値"].rolling(sma_period).min()
    high_max = ref["高値"].rolling(sma_period).max()
    stoch_k = 100 * (ref["ref_base"] - low_min) / (high_max - low_min)
    ref["ref_signal_stoch"] = stoch_k.shift(start_days)

    if signal_type != "Test":
        ref["ref_signal"] = ref[f"ref_signal_{signal_type}"]
    else:
        corr_abs = 0
        for signal_type_1, signal_type_2 in combinations(SignalType, 2):
            signal_1 = ref[f"ref_signal_{signal_type_1}"]
            signal_2 = ref[f"ref_signal_{signal_type_2}"]

            for signal in (-1, 1):
                ref["tmp_product"] = signal_1 * signal_2
                ref["tmp_signal"] = ref["tmp_product"].where(ref["tmp_product"] * signal > 0)
                if ref["tmp_signal"].count() < MIN_TRADE_COUNT:
                    continue

                merged_tmp = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))
                corr_tmp = merged_tmp["target_change_pct"].corr(merged_tmp["tmp_signal"])
                if abs(corr_tmp) > abs(corr_abs):
                    corr_abs = corr_tmp
                    ref["ref_signal"] = ref["tmp_signal"]
                del ref["tmp_product"]
                del ref["tmp_signal"]

    # === 日付で結合（inner join）===
    merged = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))

    corr = merged["target_change_pct"].corr(merged["ref_signal"])
    if CALC_ONLY_CORRELATION is True:
        return None, corr

    # Refの終値確定後、次の取引日にTargetを仕掛ける


    # === 売買シミュレーション ===
    results = []

    TRADE_COST = 0.0#TARGET_LIST[target_name]
    POS_NAME = ["long", "short"]
    POS_RATE = [1, -1]
    OPERATORS = [operator.gt, operator.lt]
    OPERATORS_COUNTER = [operator.lt, operator.gt]

    # iterrows は行ごとに Series を生成して遅いため、列を先に取り出しておく
    dates = merged["日付"].to_list()                            # Timestamp のまま保持
    exit_dates = merged["exit_date"].to_list()                    # Timestamp のまま保持
    target_closes = merged["target_base"].to_numpy()
    ref_signals = merged["ref_signal"].to_numpy()
    target_shifts = merged["target_exit"].to_numpy()
    target_changes = merged["target_change"].to_numpy()

    for idx in range(len(merged)):
        date = dates[idx]
        target_close = target_closes[idx]
        ref_signal = ref_signals[idx]
        profit_ls = [None, None]
        profit_ls_pct = [None, None]

        for i in range(2):
            if COUNTER_TRADE and not OPERATORS_COUNTER[i](ref_signal, -POS_RATE[i] * RISE_PERCENT):
                continue
            if not COUNTER_TRADE and not OPERATORS[i](ref_signal, POS_RATE[i] * RISE_PERCENT):
                continue

            entry_price = target_close
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

    return df_results, corr


def run_one(task):
    """ワーカープロセスで実行される単位。集計まで済ませて軽い dict だけ返す。"""
    ref_name, target_name, signal_type, ref_lag_days, hold_days, start_days, sma_period = task

    result_base = {}
    df_results, corr = calc_trade_results(ref_name, target_name, signal_type, ref_lag_days, hold_days, start_days, sma_period)
    if corr is not None:
        result_base = {
            "target": target_name,
            "ref": ref_name,
            "signal_type": signal_type,
            "ref_lag_days": ref_lag_days,
            "hold_days": hold_days,
            "start_days": start_days,
            "correlation": corr,
        }
        if CALC_ONLY_CORRELATION is True:
            return result_base
    
    if df_results is None or df_results.empty:
        return None

    trade_count = len(df_results)
    if trade_count < MIN_TRADE_COUNT:
        return None

    # long / short の片方が一度も成立しない場合、列が object dtype になり
    # .mean() が TypeError を投げるため、明示的に数値化しておく
    for c in ["profit_long", "profit_long_pct", "profit_short", "profit_short_pct"]:
        df_results[c] = pd.to_numeric(df_results[c], errors="coerce")


    long_count = int((df_results["position"] == "long").sum())
    short_count = int((df_results["position"] == "short").sum())

    total_profit = df_results["profit"].sum()
    average_pct = df_results["profit_pct"].mean()
    std_pct = df_results["profit_pct"].std(ddof=1)
    average_long_pct = df_results["profit_long_pct"].mean()
    average_short_pct = df_results["profit_short_pct"].mean()
    win_rate = (df_results["profit"] > 0).mean() * 100
    year_summary = df_results.attrs["year_summary"]
    year_profits = year_summary["profit"]
    positive_year_ratio = (year_profits > 0).mean() * 100
    worst_year_profit = year_profits.min()
    #corr_t = corr * (trade_count - 2) ** 0.5 / (1 - corr ** 2) ** 0.5 if abs(corr) < 1 else float("nan")

    result_sub = {
        "trade_count": trade_count,
        "long_count": long_count,
        "short_count": short_count,
        "win_rate": win_rate,
        "total_profit": total_profit,
        "positive_year_ratio": positive_year_ratio,
        "worst_year_profit": worst_year_profit,
        "average_pct": average_pct,
        "std_pct": std_pct,
        "average_long_pct": average_long_pct,
        "average_short_pct": average_short_pct,
    }

    return result_base | result_sub


def main():
    start_time = datetime.datetime.now()
    print(f"ワーカー数: {MAX_WORKERS}")

    tasks = [
        (ref_name, target_name, signal_type, ref_lag_days, hold_days, start_days, sma_period)
        for ref_name in REF_LIST
        for target_name in TARGET_LIST
        for signal_type in SIGNAL_TYPE_LIST
        for ref_lag_days in REF_LAG_DAYS_LIST
        for hold_days in HOLD_DAYS_LIST
        for start_days in START_DAYS_LIST
        for sma_period in SMA_PERIOD_LIST
    ]

    ranking_results = []

    if USE_PROCESS_POOL:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(run_one, task) for task in tasks]

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    ranking_results.append(result)
    else:
        for task in tasks:
            result = run_one(task)
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
