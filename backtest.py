import operator
import time
import pandas as pd
from itertools import combinations

from backtest_config import BackTestConfig, SignalType
from market_data import MarketData


def calc_trade_results(config : BackTestConfig, ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, hold_days, start_days, sma_period):
    if hold_days < 1:
        raise ValueError("hold_daysは1以上を指定してください。")
    if start_days < 1:
        raise ValueError("start_daysは1以上を指定してください。")

    if config.trade_code_type == "same" and ref_name != target_name:
        return None, None, None
    if config.trade_code_type == "not_same" and ref_name == target_name:
        return None, None, None


    # 事前計算しておいた指標を取り出す。タスクごとに計算し直さない。
    # このあと ref/target に列を追加するので、キャッシュ本体を汚さないよう
    # コピーを受け取る。
    ref = _REF_CACHE[(ref_name, start_days, sma_period)].copy()
    target = _TARGET_CACHE[(target_name, hold_days)].copy()

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
    TRADE_COST = config.cost_of(target_name)
    # スワップ（％／日）。ロング保有時に受け取る率で、ショートは符号が反転する。
    # 保有日数は暦日で数える（スワップは休場日にも発生するため）。
    SWAP_PCT_PER_DAY = config.swap_of(target_name)
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
            if SWAP_PCT_PER_DAY:
                # 保有した暦日数ぶんのスワップを加減する。
                # long(+1) は設定値のまま、short(-1) は符号が反転する。
                holding_days = (exit_date - date).days
                swap_pct = POS_RATE[i] * SWAP_PCT_PER_DAY * holding_days
                profit += swap_pct / 100 * entry_price
            if use_excess_return:
                # ドリフトを価格に換算して差し引く。
                # long（+1）は追い風を、short（-1）は逆風を取り除く。
                profit -= POS_RATE[i] * drift_pct / 100 * entry_price
            if config.extra_cost_pct:
                # 一律の追加コスト。現実の摩擦の上乗せ分を entry 価格基準で引く。
                # 摩擦なので long/short どちらでも必ずマイナス（符号を持たせない）。
                profit -= config.extra_cost_pct / 100 * entry_price
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


# ワーカープロセスごとに共有する config と事前計算済みの指標。
# タスクごとに送ると転送コストがかさむため、
# ProcessPoolExecutor の initializer で1回だけ渡してここに置く。
_WORKER_CONFIG = None
_REF_CACHE = {}
_TARGET_CACHE = {}


def init_worker(config, ref_cache, target_cache):
    """ワーカー起動時に config と指標キャッシュを受け取って保持する。"""
    global _WORKER_CONFIG, _REF_CACHE, _TARGET_CACHE
    _WORKER_CONFIG = config
    _REF_CACHE = ref_cache
    _TARGET_CACHE = target_cache


def run_one_shared(task):
    """initializer で渡された config を使って run_one を呼ぶ。
    map に渡せるよう引数を task だけにしてある。"""
    return run_one(_WORKER_CONFIG, task)


def run_one(config, task):
    """ワーカープロセスで実行される単位。集計まで済ませて軽い dict だけ返す。"""
    task_start = time.perf_counter() if config.output_task_time else None

    ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, hold_days, start_days, sma_period = task

    result_base = {}
    df_results, corr, other_message = calc_trade_results(config, ref_name, target_name, signal_type, counter_trade, use_excess_return, threshold_width, hold_days, start_days, sma_period)
    if corr is not None:
        result_base = {
            "target": target_name,
            "ref": ref_name,
            "signal_type": signal_type,
            "counter_trade": counter_trade,
            "use_excess_return": use_excess_return,
            "threshold_width": threshold_width,
            "hold_days": hold_days,
            "start_days": start_days,
            "sma_period": sma_period,
            "correlation": corr,
            "other_message": other_message,
        }
    
    if df_results is None or df_results.empty:
        return None

    # long / short の片方が一度も成立しない場合、列が object dtype になり
    # .mean() が TypeError を投げるため、明示的に数値化しておく
    for c in ["profit_long", "profit_long_pct", "profit_short", "profit_short_pct"]:
        df_results[c] = pd.to_numeric(df_results[c], errors="coerce")

    # ランキング集計の対象期間で絞る。config.ranking_period が空なら全期間（従来どおり）。
    # ここで絞るのは順位付けに使う統計（t_value/average/trade_count 等）だけ。
    # 期間別列（period_years）は下で常に全期間の df_results から作るので、
    # 「後半で強く前半で弱い」を同時に確認できる。
    if config.ranking_period:
        rp_start, rp_end = config.ranking_period
        df_rank = df_results[
            (df_results["year"] >= rp_start) & (df_results["year"] <= rp_end)
        ]
    else:
        df_rank = df_results

    trade_count = len(df_rank)
    if trade_count < config.min_trade_count:
        return None

    long_count = int((df_rank["position"] == "long").sum())
    short_count = int((df_rank["position"] == "short").sum())

    total_profit = df_rank["profit"].sum()
    average_pct = df_rank["profit_pct"].mean()
    std_pct = df_rank["profit_pct"].std(ddof=1)
    average_long_pct = df_rank["profit_long_pct"].mean()
    average_short_pct = df_rank["profit_short_pct"].mean()
    win_rate = (df_rank["profit"] > 0).mean() * 100
    # 陽性年比率・最悪年も対象期間で数える（対象期間内の年ごと損益から算出）。
    year_profits = df_rank.groupby("year")["profit"].sum()
    positive_year_ratio = (year_profits > 0).mean() * 100 if len(year_profits) else float("nan")
    worst_year_profit = year_profits.min() if len(year_profits) else float("nan")
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

    result = result_base | result_sub | period_result
    if config.output_task_time:
        result["task_elapsed_seconds"] = time.perf_counter() - task_start

    return result


