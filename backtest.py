import operator
import pandas as pd
from pathlib import Path
from enum import StrEnum
from itertools import combinations

from backtest_config import BackTestConfig

# === 設定 ===
class SignalType(StrEnum):
    CHANGE = "change"
    SMA = "sma"
    BB = "bb"
    MACD = "macd"
    RSI = "rsi"
    DI = "di"
    #ADX = "adx"
    STOCH = "stoch"
    STREAK = "streak"

# ワーカープロセスごとに、読み込み済みのCSVデータを保持する
DATA_CACHE = {}

DATA_FOLDER = Path(__file__).resolve().parent / "stock-data" / "Manual"
REQUIRED_COLUMNS = ["日付", "終値", "高値", "安値"]


# === データ読み込み ===
def load_data(path):
    if path in DATA_CACHE:
        return DATA_CACHE[path].copy()

    if not DATA_FOLDER.is_dir():
        raise FileNotFoundError(
            f"データフォルダが見つかりません: {DATA_FOLDER}"
        )

    files = sorted(DATA_FOLDER.rglob(f"{path}.csv"))

    if not files:
        raise FileNotFoundError(f"{path}.csv が見つかりませんでした: {DATA_FOLDER}")
    if len(files) > 1:
        file_list = "\n".join(str(file) for file in files)
        raise RuntimeError(f"{path}.csv が複数見つかりました:\n{file_list}")

    csv_path = files[0]
    df = pd.read_csv(csv_path)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(
            f"{csv_path}: 必須列がありません: {', '.join(missing_columns)}"
        )

    parsed_dates = pd.to_datetime(df["日付"], errors="coerce")
    invalid_date_rows = df.index[df["日付"].notna() & parsed_dates.isna()]
    if len(invalid_date_rows) > 0:
        row_numbers = ", ".join(str(index + 2) for index in invalid_date_rows[:5])
        raise ValueError(f"{csv_path}: 日付を変換できません（行: {row_numbers}）")
    df["日付"] = parsed_dates

    for column in ["終値", "高値", "安値"]:
        numeric_values = pd.to_numeric(df[column], errors="coerce")
        invalid_rows = df.index[df[column].notna() & numeric_values.isna()]
        if len(invalid_rows) > 0:
            row_numbers = ", ".join(str(index + 2) for index in invalid_rows[:5])
            raise ValueError(
                f"{csv_path}: {column}を数値に変換できません（行: {row_numbers}）"
            )
        df[column] = numeric_values

    # 他の列（出来高など）の欠損で行が消えると shift() の「何営業日前」がズレるため、
    # 実際に使う列だけを対象にする
    df = df.dropna(subset=REQUIRED_COLUMNS)
    if df.empty:
        raise ValueError(f"{csv_path}: 有効な価格データがありません")

    duplicate_dates = df["日付"].duplicated(keep=False)
    if duplicate_dates.any():
        dates = df.loc[duplicate_dates, "日付"].dt.strftime("%Y-%m-%d").unique()
        date_list = ", ".join(dates[:5])
        raise ValueError(f"{csv_path}: 日付が重複しています: {date_list}")

    invalid_price_range = df["高値"] < df["安値"]
    if invalid_price_range.any():
        row_numbers = ", ".join(
            str(index + 2) for index in df.index[invalid_price_range][:5]
        )
        raise ValueError(f"{csv_path}: 高値が安値を下回っています（行: {row_numbers}）")

    df = df.sort_values("日付")
    DATA_CACHE[path] = df

    # 計算中に列を追加するため、キャッシュ本体ではなくコピーを返す
    return DATA_CACHE[path].copy()


def calc_trade_results(config : BackTestConfig, ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, ref_lag_days, hold_days, start_days, sma_period):
    if ref_lag_days < 1:
        raise ValueError("ref_lag_daysは1以上を指定してください。")
    if hold_days < 1:
        raise ValueError("hold_daysは1以上を指定してください。")
    if start_days < 1:
        raise ValueError("start_daysは1以上を指定してください。")

    if config.trade_code_type == "same" and ref_name != target_name:
        return None, None, None
    if config.trade_code_type == "not_same" and ref_name == target_name:
        return None, None, None

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
    
    # macd（ヒストグラムのゼロ交差を +1 / -1 / 0 で表す）
    # macd 本体は価格スケールに比例するため、値そのものを閾値と比べると
    # 銘柄ごとに判定基準が変わってしまう。符号が変わった瞬間だけを見れば
    # スケールに依存しないので、交差をイベントとして扱う。
    ema_fast = ref["ref_base"].ewm(span=12, adjust=False).mean()
    ema_slow = ref["ref_base"].ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal_line = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal_line
    prev_hist = macd_hist.shift(1)
    # マイナス→プラスで +1、プラス→マイナスで -1、それ以外は 0。
    # 立ち上がり（NaN）の区間は交差と判定しない。
    macd_cross = (
        ((macd_hist > 0) & (prev_hist <= 0)).astype(float)
        - ((macd_hist < 0) & (prev_hist >= 0)).astype(float)
    )
    macd_cross = macd_cross.where(macd_hist.notna() & prev_hist.notna())
    ref["ref_signal_macd"] = macd_cross.shift(start_days)

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

    # ADX（トレンドの強さ。方向を持たないので単独売買には使わず、
    # フィルタ専用として使う。config の filter_signal_type で指定する）
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(sma_period).mean()
    ref["ref_signal_adx"] = adx.shift(start_days)

     # stoch
    low_min = ref["安値"].rolling(sma_period).min()
    high_max = ref["高値"].rolling(sma_period).max()
    stoch_k = 100 * (ref["ref_base"] - low_min) / (high_max - low_min)
    ref["ref_signal_stoch"] = stoch_k.shift(start_days)

    # streak（何日連続で上げ／下げたか）
    # 3日連続で上げたら +3、2日連続で下げたら -2 のように符号付きで表す。
    # 前日比が変わらない日（0）は連続を途切れさせ、その日は 0 とする。
    # 閾値 width=2.5 なら「3日以上の連続」でシグナル成立となる。
    price_diff = ref["ref_base"].diff()
    diff_sign = (price_diff > 0).astype(int) - (price_diff < 0).astype(int)
    # 符号が切り替わったところで区切り、その区間内での通し番号を連続日数とする
    streak_group = (diff_sign != diff_sign.shift(1)).cumsum()
    streak_length = diff_sign.groupby(streak_group).cumcount() + 1
    ref["ref_signal_streak"] = (streak_length * diff_sign).shift(start_days)

    other_message = ""

    if signal_type != "Test":
        ref["ref_signal"] = ref[f"ref_signal_{signal_type}"]
    else:
        corr_abs = 0
        for signal_type_1, signal_type_2 in combinations(SignalType, 2):
            signal_1 = ref[f"ref_signal_{signal_type_1}"]
            signal_2 = ref[f"ref_signal_{signal_type_2}"]
            ref["tmp_product"] = signal_1 * signal_2

            for signal in (-1, 1):
                ref["tmp_signal"] = ref["tmp_product"].where(ref["tmp_product"] * signal > 0)
                if ref["tmp_signal"].count() < config.min_trade_count:
                    del ref["tmp_signal"]
                    continue

                merged_tmp = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))
                corr_tmp = merged_tmp["target_change_pct"].corr(merged_tmp["tmp_signal"])
                if abs(corr_tmp) > abs(corr_abs):
                    corr_abs = corr_tmp
                    ref["ref_signal"] = ref["tmp_signal"]
                    other_message = f"（Test: {signal_type_1} * {signal_type_2} * {signal}）"
                del ref["tmp_signal"]

            del ref["tmp_product"]

    # === 日付で結合（inner join）===
    merged = pd.merge(ref, target, on="日付", suffixes=("_Ref", "_Target"))

    corr = merged["target_change_pct"].corr(merged["ref_signal"])

    # Refの終値確定後、次の取引日にTargetを仕掛ける


    # === 売買シミュレーション ===
    results = []

    # 売買コスト（値幅）。仕掛け時に1回だけ引く片道コスト。
    # target_list が銘柄->コストの辞書ならその値、リスト等で引けなければ 0。
    try:
        TRADE_COST = float(config.target_list[target_name])
    except (KeyError, TypeError, ValueError):
        TRADE_COST = 0.0
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

    # 指標ごとの閾値。center を中心に ±width を超えたら売買シグナルとする。
    # center=0 の指標（bb, change, sma, macd, di）は従来と同じ挙動になる。
    # threshold_width は引数で受け取る（config で複数候補を指定できるため）
    threshold_center = config.center_of(signal_type)

    # 売買フィルタ。指定された指標（adx など）の値が filter_max 以下の日だけ
    # エントリーする。adx は方向を持たないので単独では売買に使えないが、
    # 「トレンドが弱い（レンジ）ときだけ逆張りする」という絞り込みに使える。
    # filter_signal_type が空ならフィルタなし（従来と同じ挙動）。
    filter_values = None
    if config.filter_signal_type:
        filter_column = f"ref_signal_{config.filter_signal_type}"
        if filter_column not in merged.columns:
            raise KeyError(f"フィルタ用の列 {filter_column} がありません。")
        filter_values = merged[filter_column].to_numpy()

    # 超過リターン評価用のドリフト。
    # その銘柄を hold_days だけ単に保有した場合の平均変動率を求める。
    # long はこの分の追い風を、short は逆風を受けているので、
    # 各トレードから POS_RATE 倍して差し引けば方向バイアスを除去できる。
    drift_pct = 0.0
    if use_excess_return:
        drift_pct = merged["target_change_pct"].mean()
        if pd.isna(drift_pct):
            drift_pct = 0.0

    # 重複補正用: 方向ごと（0=long, 1=short）に次のエントリー可能日を保持する。
    # no_overlap=True のとき、決済日より前は同方向の新規を建てない。
    # long/short は独立に管理する（両建てあり）。
    next_entry_ok_date = [None, None]

    for idx in range(len(merged)):
        date = dates[idx]
        target_close = target_closes[idx]
        ref_signal = ref_signals[idx]
        profit_ls = [None, None]
        profit_ls_pct = [None, None]

        # フィルタが有効なら、条件を満たさない日はエントリーしない。
        # NaN（計算できない期間）も条件を満たさないものとして除外する。
        if filter_values is not None:
            filter_value = filter_values[idx]
            if pd.isna(filter_value) or filter_value > config.filter_max:
                continue

        # 中心からの距離で判定する（rsi などは center=50）
        signal_dev = ref_signal - threshold_center

        for i in range(2):
            if counter_trade and not OPERATORS_COUNTER[i](signal_dev, -POS_RATE[i] * threshold_width):
                continue
            if not counter_trade and not OPERATORS[i](signal_dev, POS_RATE[i] * threshold_width):
                continue

            # 重複補正: この方向をまだ保有中なら新規を建てない
            if (
                config.no_overlap
                and next_entry_ok_date[i] is not None
                and date < next_entry_ok_date[i]
            ):
                continue

            entry_price = target_close
            exit_price = target_shifts[idx]

            if pd.isna(exit_price):
                continue

            exit_date = exit_dates[idx]

            # 実際の決済日まで同方向の新規を建てないようロックする。
            # RefとTargetで休場日が異なっても、結合後の行数には依存しない。
            if config.no_overlap:
                next_entry_ok_date[i] = exit_date
            profit = POS_RATE[i] * target_changes[idx] - TRADE_COST
            if use_excess_return:
                # ドリフトを価格に換算して差し引く。
                # long（+1）は追い風を、short（-1）は逆風を取り除く。
                profit -= POS_RATE[i] * drift_pct / 100 * entry_price
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

    return df_results, corr, other_message


def run_one(config, task):
    """ワーカープロセスで実行される単位。集計まで済ませて軽い dict だけ返す。"""
    ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, ref_lag_days, hold_days, start_days, sma_period = task

    result_base = {}
    df_results, corr, other_message = calc_trade_results(config, ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, ref_lag_days, hold_days, start_days, sma_period)
    if corr is not None:
        result_base = {
            "target": target_name,
            "ref": ref_name,
            "signal_type": signal_type,
            "counter_trade": counter_trade,
            "use_excess_return": use_excess_return,
            "threshold_width": threshold_width,
            "ref_lag_days": ref_lag_days,
            "hold_days": hold_days,
            "start_days": start_days,
            "sma_period": sma_period,
            "correlation": corr,
            "other_message": other_message,
        }
    
    if df_results is None or df_results.empty:
        return None

    trade_count = len(df_results)
    if trade_count < config.min_trade_count:
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
    # t値: 平均損益がノイズと区別できるかの目安。
    # 平均が大きく、ばらつきが小さく、サンプルが多いほど高くなる。
    # 「平均は良いが少数サンプル」「平均は良いがσが巨大」といった
    # 見かけ倒しの組み合わせを下位に沈められる。
    # ただしトレード間・銘柄間の相関までは補正できないため、
    # 絶対的な有意性判定ではなく相対的な順位付けとして使う。
    if std_pct and std_pct > 0 and trade_count > 1:
        t_value = average_pct / std_pct * (trade_count ** 0.5)
    else:
        t_value = float("nan")

    # 期間別の成績。config の period_years で区切った各期間について
    # average_pct と trade_count を出す。全期間で安定してプラスかを
    # 目で確認するための材料。
    # 注意: 全期間のデータを見た上で上位を選んでいるので、これは
    # 「過剰適合を検出する」ものではなく「安定性を眺める」ためのもの。
    # trade_count も併記するのは、少数トレードの期間の数値を
    # 信用しすぎないため。
    period_result = {}
    if config.period_years:
        years = sorted(config.period_years)
        for index, start_year in enumerate(years):
            if index + 1 < len(years):
                end_year = years[index + 1] - 1
                label = f"{start_year}_{end_year}"
                target_rows = df_results[
                    (df_results["year"] >= start_year) & (df_results["year"] <= end_year)
                ]
            else:
                label = f"{start_year}_"
                target_rows = df_results[df_results["year"] >= start_year]
            count = len(target_rows)
            period_result[f"average_pct_{label}"] = (
                target_rows["profit_pct"].mean() if count else float("nan")
            )
            period_result[f"trade_count_{label}"] = count

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
        "t_value": t_value,
        "average_long_pct": average_long_pct,
        "average_short_pct": average_short_pct,
    }

    return result_base | result_sub | period_result

