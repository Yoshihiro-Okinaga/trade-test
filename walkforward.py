"""
walk-forward 検証

やること: 「戦略を選ぶ期間」と「その戦略の成績を測る期間」を時間で分離し、
過去だけで選んだ戦略を、その直後の未知期間で評価する。これを時間軸に沿って
何度も繰り返し、未知期間の成績だけをつなぎ合わせて「実運用相当」の成績を出す。

なぜ必要か:
    main.py は全期間の t値で上位を選ぶため、全期間を見た上で勝者を選ぶことになり、
    優位性を大きく過大評価する（＝過剰最適化）。walk-forward は選抜に使う情報を
    「その時点までの過去」に限定するので、この水増しを取り除ける。

設計方針:
    売買シミュレーション本体（backtest.calc_trade_results）はそのまま再利用する。
    各パラメータ組み合わせについて、全履歴のトレードを1回だけ計算し、その損益率を
    「(エントリー年, 決済年) ごとの十分統計量」に畳んで持ち帰る。
    学習・検証では、エントリーから決済までがその期間内で完結したトレードだけを
    足し合わせる。年境界をまたぐトレードはどちらの期間にも含めない。

制約・注意:
    - フォールドは年単位で区切り、期間内で完結したトレードだけを使う。
    - use_excess_return=true のドリフト（相場方向の除去量）は、元コードでは全期間平均
      で計算される。厳密な leak-free を求めるなら use_excess_return=[false] で回すこと。
      本モジュールはそれ以外の未来情報の混入は排除している。
    - t値は各トレードを独立とみなす近似（トレード間・銘柄間の相関は補正しない）。
      main.py と同じ前提なので、相対比較の目安として使うこと。

使い方:
    config.toml に [walkforward] セクションを足してから、
        python walkforward.py
    出力:
        walkforward_{metric}.csv  … 統合表（1行=1未知トレード＋その戦略メタ＋学習成績）。
                                     旧 selection / summary / equity はこの表の集計ビューに相当し、
                                     フォールド別成績・選抜一覧・累積リターンはここから再現できる。
                                     OOSトレードが0だった選抜戦略も、トレード列を空にして1行残す。
    コンソール: 残存率・未知成績・フォールド別成績・閾値スキャン・最大ドローダウン

    実運用シグナル（別モード）:
        python walkforward.py live
    直近 train_years 年で「今の最良戦略」を選び、それが現在出しているシグナル
    （オープン建玉・本日の新規シグナル・直近決済）を live_signals.csv とコンソールに出す。
    ranking_period に関係なく常に最新データを基準にする。検証(上)とは別の実行。
"""
import os
import sys
import math
import csv
import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# pandas や backtest / market_data といった重い依存は、純粋なロジック関数を
# 単体テストしやすいよう、モジュール読み込み時ではなく関数内で import する。

MAX_WORKERS = min(32, os.cpu_count() or 1)


def default_save_dir():
    """通常実行時の出力先を返す。"""
    if sys.platform == "darwin":
        return Path.home() / "Dropbox" / "Private" / "trade_test_results"
    return Path("./")

# ============================================================================
# 純粋なロジック（外部依存なし。ここだけで単体テストできる）
# ============================================================================

def make_folds(min_year, max_year, train_years, test_years, step_years, mode):
    """年境界でフォールドを作る。

    各フォールドは (train_start, train_end, test_start, test_end) の年タプル。
    最初の検証期間は「初期学習期間ぶん」だけ後ろから始まる。
    step_years=test_years にすると検証期間が重ならずに時間軸を敷き詰める
    （＝各未知トレードが1回だけ数えられる）。
    mode="anchored" は学習開始を min_year に固定して期間を伸ばす。
    mode="rolling" は学習期間を固定長でスライドさせる。
    """
    if train_years < 1 or test_years < 1 or step_years < 1:
        raise ValueError("train_years / test_years / step_years は1以上にしてください。")

    folds = []
    test_start = min_year + train_years
    while test_start + test_years - 1 <= max_year:
        test_end = test_start + test_years - 1
        train_end = test_start - 1
        if mode == "anchored":
            train_start = min_year
        elif mode == "rolling":
            train_start = test_start - train_years
        else:
            raise ValueError(f"mode は 'anchored' か 'rolling'。指定値: {mode!r}")
        folds.append((train_start, train_end, test_start, test_end))
        test_start += step_years
    return folds


def period_year_stats(period_stats, lo, hi):
    """期間内で完結したトレードを、従来どおりエントリー年別にまとめる。"""
    by_entry_year = {}
    for (entry_year, exit_year), (c, su, sq, wi) in period_stats.items():
        if not (lo <= entry_year <= exit_year <= hi):
            continue
        old_c, old_s, old_ss, old_w = by_entry_year.get(
            entry_year, (0, 0.0, 0.0, 0)
        )
        by_entry_year[entry_year] = (
            old_c + c, old_s + su, old_ss + sq, old_w + wi
        )
    return by_entry_year


def n_years_with_trades(period_stats, lo, hi):
    """期間内で完結したトレードが1件以上あるエントリー年の数を返す。"""
    return len(period_year_stats(period_stats, lo, hi))


def agg_period_stats(period_stats, lo, hi):
    """期間内で完結したトレードの十分統計量を合算する。

    entry_year >= lo かつ exit_year <= hi のトレードだけを使う。
    したがって期間の開始前に建てたトレードや、期間終了後に決済するトレードは
    IS/OOS のどちらにも混入しない。
    """
    n = s = ss = w = 0
    for (entry_year, exit_year), (c, su, sq, wi) in period_stats.items():
        if not (lo <= entry_year <= exit_year <= hi):
            continue
        n += c
        s += su
        ss += sq
        w += wi
    return n, s, ss, w


def mean_std_t(n, s, ss):
    """件数・合計・二乗和から 平均 / 標準偏差(不偏) / t値 を復元する。"""
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    mean = s / n
    if n > 1:
        var = (ss - n * mean * mean) / (n - 1)
        std = math.sqrt(var) if var > 0 else 0.0
    else:
        std = 0.0
    t = (mean / std * math.sqrt(n)) if (std > 0 and n > 1) else float("nan")
    return mean, std, t


def year_t_value(period_stats, lo, hi):
    """期間内で完結したトレードの年平均を1サンプルとして t値を計算する。

    取引数そのものではなく、複数年にわたって平均損益が安定している戦略を
    高く評価するための選抜指標。年の所属は従来どおりエントリー年を使う。
    """
    year_stats = period_year_stats(period_stats, lo, hi)
    year_means = [
        su / c
        for c, su, _sq, _wi in year_stats.values()
        if c > 0
    ]
    n_years = len(year_means)
    if n_years <= 1:
        return float("nan")

    mean = sum(year_means) / n_years
    var = sum((value - mean) ** 2 for value in year_means) / (n_years - 1)
    std = math.sqrt(var) if var > 0 else 0.0
    return (mean / std * math.sqrt(n_years)) if std > 0 else float("nan")


def score_of(metric, n, s, ss, period_stats=None, lo=None, hi=None):
    """選抜スコアを返す。

    metric:
        t_value                 : 従来の取引単位 t値
        year_t_value            : 年ごとの平均損益率を1サンプルとした t値
        lower_confidence_bound  : 平均損益 - 1標準誤差
        average_pct             : 平均損益率
        total_pct               : 損益率合計
        worst_year_pct          : 学習期間の年平均のうち最悪の年（マキシミン）
        positive_year_ratio     : 陽性年比率 × 平均（一貫性と大きさの合成）
        half_split_min          : 学習期間を前後半に割り、低い方の平均

    後半3つ（worst_year_pct / positive_year_ratio / half_split_min）は
    「学習成績の高さ」ではなく「まぐれで高く出にくい性質」を要求する指標。
    多数の候補から最大を選ぶことで生じる選抜バイアスへの対抗策として用意した。
    """
    mean, std, t = mean_std_t(n, s, ss)
    if metric == "t_value":
        return t
    if metric == "year_t_value":
        if period_stats is None or lo is None or hi is None:
            return float("nan")
        return year_t_value(period_stats, lo, hi)
    if metric == "lower_confidence_bound":
        if std <= 0 or n <= 1:
            return float("nan")
        return mean - std / math.sqrt(n)
    if metric == "average_pct":
        return mean
    if metric == "total_pct":
        return float(s)
    if metric in ("worst_year_pct", "positive_year_ratio", "half_split_min"):
        if period_stats is None or lo is None or hi is None:
            return float("nan")
        year_stats = period_year_stats(period_stats, lo, hi)
        year_means = {y: su / c for y, (c, su, _sq, _wi) in year_stats.items() if c > 0}
        if not year_means:
            return float("nan")
        if metric == "worst_year_pct":
            # どの年も食えるかを要求する。1年のまぐれ当たりで押し上がった候補を排除。
            return min(year_means.values())
        if metric == "positive_year_ratio":
            # 陽性年比率だけでは同率が多発するので、平均と掛けて大きさも反映する。
            ratio = sum(1 for v in year_means.values() if v > 0) / len(year_means)
            return ratio * mean
        # half_split_min: 学習期間を前後半に割り、両方で効いているかを要求する。
        mid = (lo + hi) / 2
        first = [v for y, v in year_means.items() if y <= mid]
        second = [v for y, v in year_means.items() if y > mid]
        if not first or not second:
            return float("nan")
        return min(sum(first) / len(first), sum(second) / len(second))
    raise ValueError(f"未知の select_metric: {metric!r}")


def select_for_fold(combos, fold, metric, select_per, top_k, min_is_trades,
                    min_is_t=0.0):
    """1フォールドぶんの選抜と未知期間評価を行い、選ばれた戦略の記録を返す。

    combos: [{"task": (...), "target": name, "periods": {(entry_year, exit_year):(n,s,ss,w)}}, ...]
    min_is_t: 品質ゲート。学習期間の t値がこの値未満の候補は選抜対象から外す。
              その結果、良い候補が無い銘柄はその期間「見送り」となり張らない。
              0.0（既定）ならゲート無効で従来どおり全銘柄に張る。t値は選抜時点で
              分かる量なので、このゲートは未来情報を使わない（leak なし）。
    戻り値: 各選抜について、学習期間の成績と検証(未知)期間の成績を持つ dict のリスト。

    注: 学習統計はすべて等重き（全トレードを同じ1票で扱う）。かつて試した年減衰
    （直近重視）は、sma=200 のようにトレードが期間後半に偏る戦略で is_mean_pct を
    凍結させ、is_t だけを膨らませて偽の高スコアを与える副作用があったため、本番選抜
    からは外した。時間構造の診断は discriminate.py の半減期スイープで行う。
    """
    train_start, train_end, test_start, test_end = fold

    scored = []
    for combo in combos:
        n, s, ss, w = agg_period_stats(combo["periods"], train_start, train_end)
        if n < min_is_trades:
            continue
        # 品質ゲート: 学習期間の t値が基準に満たない候補は捨てる。
        # min_is_t=0.0 のときは何も捨てず従来の挙動を保つ（NaN t を巻き込まない）。
        if min_is_t > 0.0:
            _, _, is_t = mean_std_t(n, s, ss)
            if math.isnan(is_t) or is_t < min_is_t:
                continue
        score = score_of(
            metric, n, s, ss, combo["periods"], train_start, train_end
        )
        if score is None or (isinstance(score, float) and math.isnan(score)):
            continue
        scored.append((score, combo, n, s, ss))

    # 決定的に並べる。スコア降順、同点は task タプルで安定させる
    # （実行ごとに順位がブレて出力 diff が壊れるのを防ぐ）。
    scored.sort(key=lambda row: (-row[0], row[1]["task"]))

    if select_per == "global":
        selected = scored[:top_k]
    elif select_per == "target":
        per_target = {}
        selected = []
        for row in scored:
            target = row[1]["target"]
            bucket = per_target.setdefault(target, 0)
            if bucket < top_k:
                selected.append(row)
                per_target[target] = bucket + 1
    else:
        raise ValueError(f"select_per は 'target' か 'global'。指定値: {select_per!r}")

    records = []
    for score, combo, is_n, is_s, is_ss in selected:
        is_mean, is_std, is_t = mean_std_t(is_n, is_s, is_ss)
        oos_n, oos_s, oos_ss, oos_w = agg_period_stats(combo["periods"], test_start, test_end)
        oos_mean = (oos_s / oos_n) if oos_n > 0 else float("nan")
        records.append({
            "train_start": train_start, "train_end": train_end,
            "test_start": test_start, "test_end": test_end,
            "task": combo["task"], "target": combo["target"],
            "is_trades": is_n, "is_mean_pct": is_mean, "is_t": is_t,
            "is_years": n_years_with_trades(combo["periods"], train_start, train_end),
            "oos_trades": oos_n, "oos_sum": oos_s, "oos_sumsq": oos_ss,
            "oos_wins": oos_w, "oos_mean_pct": oos_mean,
        })
    return records


# ============================================================================
# シミュレーション本体の再利用（重い依存はここで import）
# ============================================================================

def collect_period_stats(task):
    """1つのパラメータ組み合わせについて全履歴を計算し、
    損益率を (entry_year, exit_year) ごとの十分統計量に畳んで返す。
    config と指標キャッシュは backtest.init_worker が仕込んだグローバルを使う。
    """
    import backtest  # ワーカー側で解決

    config = backtest._WORKER_CONFIG
    df, _corr, _msg = backtest.calc_trade_results(config, False, *task)
    if df is None or df.empty:
        return None

    period_stats = {}
    entry_years = df["entry_year"].to_numpy()
    exit_years = df["exit_year"].to_numpy()
    pct = df["profit_pct"].to_numpy()
    for entry_year, exit_year, p in zip(entry_years, exit_years, pct):
        key = (int(entry_year), int(exit_year))
        c, s, ss, w = period_stats.get(key, (0, 0.0, 0.0, 0))
        value = float(p)
        period_stats[key] = (
            c + 1, s + value, ss + value * value, w + (1 if value > 0 else 0)
        )

    return {
        "task": tuple(task),
        "target": task[1],
        "periods": period_stats,
    }


def build_tasks(config):
    """main.py と同じ組み合わせを作る（閾値は指標ごとの候補を展開する）。"""
    return [
        (ref_name, target_name, signal_type, counter_trade, use_excess_return,
         threshold_width, hold_days, start_days, sma_period)
        for ref_name, target_name in config.iter_ref_target()
        for signal_type in config.signal_type_list
        for counter_trade in config.counter_trade
        for use_excess_return in config.use_excess_return
        for threshold_width in config.widths_of(signal_type)
        for hold_days in config.hold_days_list
        for start_days in config.start_days_list
        for sma_period in config.sma_period_list
    ]


def read_wf_params(config_data):
    """[walkforward] セクションを既定値つきで読む。無ければ全て既定。"""
    wf = config_data.get("walkforward", {})
    test_years = int(wf.get("test_years", 2))
    return {
        "train_years": int(wf.get("train_years", 8)),
        "test_years": test_years,
        # 既定は検証期間ぶんスライド＝未知期間を重ねない
        "step_years": int(wf.get("step_years", test_years)),
        "mode": wf.get("mode", "anchored"),
        "select_metric": wf.get("select_metric", "t_value"),
        "select_per": wf.get("select_per", "target"),
        "select_top_k": int(wf.get("select_top_k", 1)),
        "min_is_trades": int(wf.get("min_is_trades", 30)),
        # 品質ゲート: 各銘柄の最良候補でも学習期間の t値がこの値未満なら、
        # その銘柄はその期間は見送る（張らない）。0.0 でゲート無効＝従来どおり。
        "min_is_t": float(wf.get("min_is_t", 0.0)),
    }


# ============================================================================
# エクイティカーブ / 最大ドローダウン / 閾値スキャン
# ============================================================================

def max_drawdown(cumulative):
    """累積系列（各点=それまでの損益合計）から最大ドローダウンを返す。

    開始時点の累積損益 0 も山として扱う。peak_idx が None の場合は、
    最大DDの山が最初のトレードより前（開始時点）にあることを表す。
    戻り値 (max_dd, peak_idx, trough_idx)。max_dd は下落幅で常に非負。
    """
    peak = 0.0
    cur_peak_i = None
    max_dd = 0.0
    mdd_peak = None
    mdd_trough = None

    for i, value in enumerate(cumulative):
        if value > peak:
            peak = value
            cur_peak_i = i

        dd = peak - value
        if dd > max_dd:
            max_dd = dd
            mdd_peak = cur_peak_i
            mdd_trough = i
    return max_dd, mdd_peak, mdd_trough


def build_equity(trades):
    """未知トレードを実現日(exit_date)昇順に並べ、profit_pct を加算した累積系列
    （各取引を等額・非複利で足したエクイティ）と統計を返す。
    trades: [{"exit_date":..., "entry_date":..., "profit_pct":float, ...}, ...]"""
    ordered = sorted(trades, key=lambda t: (t["exit_date"], t["entry_date"]))
    cum = 0.0
    cum_sized = 0.0
    curve = []
    for t in ordered:
        size = t.get("size", 1.0)
        cum += t["profit_pct"]
        cum_sized += size * t["profit_pct"]
        row = dict(t)
        row["cumulative_pct"] = cum
        row["cumulative_sized_pct"] = cum_sized
        curve.append(row)
    cumulative = [row["cumulative_pct"] for row in curve]
    cumulative_sized = [row["cumulative_sized_pct"] for row in curve]
    if cumulative:
        mdd, pk, tr = max_drawdown(cumulative)
        final = cumulative[-1]
        mdd_s, pk_s, tr_s = max_drawdown(cumulative_sized)
        final_s = cumulative_sized[-1]
        sized_sum = sum(t.get("size", 1.0) for t in ordered)
    else:
        mdd, pk, tr, final = 0.0, None, None, 0.0
        mdd_s, pk_s, tr_s, final_s, sized_sum = 0.0, None, None, 0.0, 0.0
    return curve, {"final_pct": final, "max_dd_pct": mdd,
                   "peak_idx": pk, "trough_idx": tr, "n": len(curve),
                   "final_sized_pct": final_s, "max_dd_sized_pct": mdd_s,
                   "peak_sized_idx": pk_s, "trough_sized_idx": tr_s,
                   "size_sum": sized_sum}


def scan_thresholds(combos, folds, wf, thresholds):
    """min_is_t を変えながら選抜し直し、未知成績のトレードオフを一覧する。
    選抜は年別統計だけで行うため再シミュレーションは不要（安価）。"""
    print("\n=== 閾値スキャン（min_is_t を変えたときの未知成績。再シミュレーション不要）===")
    print("※ この表を見て閾値を選ぶと OOS への過剰適合になります。分布の構造で決めること。")
    print(f"{'min_is_t':>9}{'選抜数':>7}{'未知取引':>9}{'未知平均':>10}{'選抜プラス率':>12}")
    for thr in thresholds:
        recs = []
        for fold in folds:
            recs.extend(select_for_fold(
                combos, fold, wf["select_metric"], wf["select_per"],
                wf["select_top_k"], wf["min_is_trades"], thr))
        n = sum(r["oos_trades"] for r in recs)
        if n == 0:
            print(f"{thr:>9.1f}{len(recs):>7}{0:>9}{'—':>10}{'—':>12}")
            continue
        s = sum(r["oos_sum"] for r in recs)
        traded = [r for r in recs if r["oos_trades"] > 0]
        pos = (sum(1 for r in traded if r["oos_mean_pct"] > 0) / len(traded) * 100
               if traded else 0.0)
        print(f"{thr:>9.1f}{len(recs):>7}{int(n):>9}{s / n:>8.3f}%{pos:>11.0f}%")


def collect_oos_trades(config, records):
    """選抜済みの各戦略を再計算し、未知(検証)期間のトレードを日付つきで集める。
    同じ task が複数フォールドで選ばれることがあるので task 単位で1回だけ計算する。"""
    import backtest
    from collections import defaultdict

    by_task = defaultdict(list)
    for r in records:
        by_task[r["task"]].append(r)

    trades = []
    for task, recs in by_task.items():
        df, _corr, _msg = backtest.calc_trade_results(config, False, *task)
        if df is None or df.empty:
            continue
        ref_s, tgt_s, sig, counter, excess, width, hold, start, sma = task
        pair = f"{task[1]} ← {task[0]}"
        for r in recs:
            ts, te = r["test_start"], r["test_end"]
            # 選抜時と同じく、検証期間内で建てて期間内で決済した
            # トレードだけをOOSエクイティへ入れる。
            sub = df[
                (df["entry_year"] >= ts)
                & (df["exit_year"] <= te)
            ]
            for row in sub.itertuples():
                trades.append({
                    "signal_date": getattr(row, "signal_date", ""),
                    "exit_date": row.exit_date,
                    "entry_date": row.entry_date,
                    "profit_pct": float(row.profit_pct),
                    "size": float(getattr(row, "size", 1.0)),
                    "pair": pair,
                    "test_period": f"{ts}-{te}",
                    # 統合表用の戦略メタ＋学習成績（equity 出力には影響しない）
                    "target": tgt_s, "ref": ref_s, "signal_type": sig,
                    "counter_trade": counter, "use_excess_return": excess,
                    "threshold_width": width, "hold_days": hold,
                    "start_days": start, "sma_period": sma,
                    "is_trades": r["is_trades"], "is_mean_pct": r["is_mean_pct"],
                    "is_t": r["is_t"], "is_years": r.get("is_years", ""),
                })
    return trades


def build_and_write_equity(config, wf, records, save_dir):
    try:
        trades = collect_oos_trades(config, records)
    except Exception as e:
        print(f"\nエクイティ計算をスキップしました（{e}）")
        return
    if not trades:
        print("\nエクイティ: 未知トレードが取得できませんでした。")
        return

    curve, stats = build_equity(trades)

    n = stats["n"]
    print("\n=== エクイティ（未知トレードを実現日で連結。等額・非複利＝1取引1単位を加算）===")
    print(f"未知トレード数       : {n:,}")
    print(f"累積リターン（合計%） : {stats['final_pct']:+.2f}%")
    print(f"1取引あたり平均       : {stats['final_pct'] / n:+.4f}%")
    print(f"最大ドローダウン      : {stats['max_dd_pct']:.2f}%（累積%ポイント）")
    if stats["max_dd_pct"] > 0:
        tr = curve[stats["trough_idx"]]
        if stats["peak_idx"] is None:
            peak_text = "開始時点（山 +0.0%）"
        else:
            pk = curve[stats["peak_idx"]]
            peak_text = (
                f"{str(pk['exit_date'])[:10]}"
                f"（山 {pk['cumulative_pct']:+.1f}%）"
            )
        print(f"  DD区間: {peak_text}"
              f" → {str(tr['exit_date'])[:10]}（谷 {tr['cumulative_pct']:+.1f}%）")

    # 出力は統合表1枚のみ（equity/selection/summary はこの表の集計ビューに相当）。
    write_unified(curve, records, wf, save_dir)


UNIFIED_COLUMNS = [
    "test_period", "target", "ref", "signal_type", "counter_trade",
    "use_excess_return", "threshold_width", "hold_days", "start_days", "sma_period",
    "is_trades", "is_mean_pct", "is_t", "is_years",
    "signal_date", "entry_date", "exit_date", "profit_pct", "cumulative_pct",
]


def write_unified(curve, records, wf, save_dir):
    """3出力を統合した1枚の表を書き出す。
    各行 = 1 OOSトレード（＋その戦略のメタ情報と学習成績）。
    OOSトレードが0だった選抜戦略も、トレード列を空にして1行残す（情報を落とさない）。
    フォールド別サマリや選抜一覧は、この表を集計/ユニーク化すれば再現できる。"""
    def num(v, fmt):
        if v is None or v == "":
            return ""
        try:
            if isinstance(v, float) and math.isnan(v):
                return ""
        except TypeError:
            pass
        return format(v, fmt)

    path = Path(save_dir) / f"walkforward_{wf['select_metric']}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(UNIFIED_COLUMNS)
        # 1) トレード行
        for row in curve:
            w.writerow([
                row.get("test_period", ""), row.get("target", ""), row.get("ref", ""),
                row.get("signal_type", ""), row.get("counter_trade", ""),
                row.get("use_excess_return", ""), row.get("threshold_width", ""),
                row.get("hold_days", ""), row.get("start_days", ""), row.get("sma_period", ""),
                row.get("is_trades", ""), num(row.get("is_mean_pct"), ".9f"),
                num(row.get("is_t"), ".9f"), row.get("is_years", ""),
                str(row.get("signal_date", ""))[:10],
                str(row.get("entry_date", ""))[:10], str(row.get("exit_date", ""))[:10],
                num(row.get("profit_pct"), ".6f"), num(row.get("cumulative_pct"), ".6f"),
            ])
        # 2) OOSトレードが0だった選抜戦略（トレード列は空で1行残す）
        for r in records:
            if r.get("oos_trades", 0) != 0:
                continue
            ref_s, tgt_s, sig, counter, excess, width, hold, start, sma = r["task"]
            w.writerow([
                f"{r['test_start']}-{r['test_end']}", tgt_s, ref_s, sig, counter,
                excess, width, hold, start, sma,
                r["is_trades"], num(r["is_mean_pct"], ".9f"),
                num(r["is_t"], ".9f"), r.get("is_years", ""),
                "", "", "", "", "",
            ])
    print(f"出力: {path}")


def write_outputs(records, folds, wf):
    # 選抜明細・エクイティは統合表 walkforward_{metric}.csv に集約済み。
    # ここではフォールド別の未知成績（旧 summary.csv 相当）をコンソールに表示する。
    per_fold = {}
    for r in records:
        key = (r["test_start"], r["test_end"])
        n, s, ss, w = per_fold.get(key, (0, 0.0, 0.0, 0))
        per_fold[key] = (n + r["oos_trades"], s + r["oos_sum"],
                         ss + r["oos_sumsq"], w + r["oos_wins"])

    print("\n=== フォールド別 未知成績 ===")
    print(f"{'期間':>11}{'取引':>7}{'平均%':>10}{'t値':>8}{'勝率%':>8}")
    for (ts, te) in sorted(per_fold):
        n, s, ss, w = per_fold[(ts, te)]
        mean, _std, t = mean_std_t(n, s, ss)
        win = (w / n * 100) if n else float("nan")
        tstr = "―" if math.isnan(t) else f"{t:.2f}"
        print(f"{f'{ts}-{te}':>11}{n:>7}{mean:>+10.4f}{tstr:>8}{win:>8.1f}")

    # --- コンソールに要点（過大評価がどれだけ剥がれたか）---
    tot_is_n = sum(r["is_trades"] for r in records)
    tot_is_sum = sum(r["is_mean_pct"] * r["is_trades"] for r in records)
    tot_n = sum(r["oos_trades"] for r in records)
    tot_s = sum(r["oos_sum"] for r in records)
    tot_ss = sum(r["oos_sumsq"] for r in records)
    tot_w = sum(r["oos_wins"] for r in records)
    is_mean = tot_is_sum / tot_is_n if tot_is_n else float("nan")
    oos_mean, oos_std, oos_t = mean_std_t(tot_n, tot_s, tot_ss)
    oos_win = (tot_w / tot_n * 100) if tot_n else float("nan")

    print("\n=== walk-forward 結果（未知期間のみ＝実運用相当）===")
    print(f"選抜回数（フォールド×銘柄）: {len(records)}")
    print(f"インサンプルで見えていた平均: {is_mean:+.4f}% / 取引")
    print(f"未知期間の平均              : {oos_mean:+.4f}% / 取引  ← これが実力")
    if tot_is_n and not math.isnan(is_mean) and abs(is_mean) > 1e-12:
        keep = oos_mean / is_mean * 100
        print(f"残存率                     : {keep:.1f}%（100%から遠いほど過剰最適化）")
    print(f"未知期間の総取引数          : {tot_n:,}")
    print(f"未知期間の t値              : {oos_t:.3f}（独立仮定の近似）")
    print(f"未知期間の勝率              : {oos_win:.2f}%")
    print(f"\n出力: walkforward_{wf['select_metric']}.csv（統合表1枚）")


def run(
    recent_closed=5,
    config_path=None,
    data_folder=None,
    save_dir=None,
    select_metric=None,
):
    import tomllib
    import backtest
    import market_data
    import backtest_config
    import numpy as np

    start_time = datetime.datetime.now()

    config_path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).parent / "config.toml"
    )
    save_dir = Path(save_dir) if save_dir is not None else default_save_dir()
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
    except FileNotFoundError:
        print(f"エラー: {config_path} が見つかりません。")
        sys.exit(1)

    config = backtest_config.BackTestConfig(config_data)
    wf = read_wf_params(config_data)
    if select_metric is not None:
        wf["select_metric"] = select_metric

    # 前提が崩れるケースを先に知らせる
    if any(bool(x) for x in config.use_excess_return):
        print("注意: use_excess_return=true のドリフトは全期間平均で計算されます。"
              "厳密な leak-free 評価には use_excess_return=[false] を推奨します。")

    print(f"ワーカー数: {MAX_WORKERS}")
    print(f"walk-forward 設定: {wf['mode']} / 学習{wf['train_years']}年 → 検証{wf['test_years']}年 "
          f"（{wf['step_years']}年ずつ前進） / 選抜={wf['select_metric']}・"
          f"{wf['select_per']}ごと上位{wf['select_top_k']} / 最小IS取引={wf['min_is_trades']}"
          + (f" / 品質ゲート min_is_t={wf['min_is_t']}" if wf['min_is_t'] > 0
             else " / 品質ゲートなし"))

    tasks = build_tasks(config)
    print(f"組み合わせ数: {len(tasks):,}")

    print("指標を事前計算しています...", flush=True)
    ref_cache, target_cache = market_data.build_caches(config, data_folder)
    print(f"事前計算 完了（ref {len(ref_cache)} 件 / target {len(target_cache)} 件）")

    # データ最終日（＝「いま」の基準日）を求める。
    last_date = None
    for _key, tdf in target_cache.items():
        d = tdf["日付"].max()
        last_date = d if last_date is None else max(last_date, d)

    # --- 全組み合わせの年別統計を集める（ここが重い。main と同じ並列化）---
    combos = []
    total = len(tasks)
    if config.use_process_pool:
        chunksize = max(1, total // (MAX_WORKERS * 8))
        with ProcessPoolExecutor(
            max_workers=MAX_WORKERS,
            initializer=backtest.init_worker,
            initargs=(config, ref_cache, target_cache),
        ) as executor:
            for done, result in enumerate(
                executor.map(collect_period_stats, tasks, chunksize=chunksize), start=1
            ):
                if result is not None:
                    combos.append(result)
                print(f"\r集計: {done}/{total}", end="", flush=True)
    else:
        backtest.init_worker(config, ref_cache, target_cache)
        for done, task in enumerate(tasks, start=1):
            result = collect_period_stats(task)
            if result is not None:
                combos.append(result)
            print(f"\r集計: {done}/{total}", end="", flush=True)
    print()

    if not combos:
        print("有効なトレードがある組み合わせがありませんでした。")
        sys.exit(1)

    # --- データに実在する年の範囲からフォールドを作る ---
    all_years = set()
    for combo in combos:
        for entry_year, exit_year in combo["periods"].keys():
            all_years.add(entry_year)
            all_years.add(exit_year)
    min_year, max_year = min(all_years), max(all_years)
    # live
    train_start = max_year - wf["train_years"] + 1
    live_fold = (train_start, max_year, max_year, max_year)
    live_records = select_for_fold(combos, live_fold, wf["select_metric"],
                                   wf["select_per"], wf["select_top_k"],
                                   wf["min_is_trades"], wf["min_is_t"])

    # ranking_period が指定されていれば、walk-forward の対象年もその範囲に収める。
    # これで「まず 2001-2020 で前進検証 → 2021 以降は最終テストまで手つかずで温存」
    # という段階的な使い方ができる（学習も検証もこの範囲内だけで行う）。
    # 空 [] なら全期間（従来どおり）。
    if config.ranking_period:
        rp_start, rp_end = config.ranking_period
        data_min, data_max = min_year, max_year
        min_year = max(min_year, rp_start)
        max_year = min(max_year, rp_end)
        print(f"ranking_period 適用: {rp_start}〜{rp_end} に限定"
              f"（データ実在範囲 {data_min}〜{data_max}）")
        if min_year > max_year:
            print("ranking_period がデータ範囲と重なりません。設定を見直してください。")
            sys.exit(1)
    folds = make_folds(min_year, max_year, wf["train_years"], wf["test_years"],
                       wf["step_years"], wf["mode"])
    if not folds:
        print(f"データ年範囲 {min_year}〜{max_year} では、学習{wf['train_years']}年＋"
              f"検証{wf['test_years']}年のフォールドを作れません。設定を見直してください。")
        sys.exit(1)
    print(f"データ年範囲: {min_year}〜{max_year} / フォールド数: {len(folds)}")

    # --- 各フォールドで選抜し、未知期間の成績を集める ---
    all_records = []
    for fold in folds:
        all_records.extend(select_for_fold(
            combos, fold, wf["select_metric"], wf["select_per"],
            wf["select_top_k"], wf["min_is_trades"], wf["min_is_t"],
        ))

    if not all_records:
        print("どのフォールドでも選抜条件を満たす戦略がありませんでした。"
              "min_is_trades や min_is_t を緩めてください。")
        sys.exit(1)

    # 品質ゲートで「張らなかった枠」がどれだけあるかを可視化（銘柄別選抜のとき）
    if wf["select_per"] == "target":
        n_targets = len({combo["target"] for combo in combos})
        max_slots = len(folds) * n_targets
        placed = len(all_records)
        skipped = max_slots - placed
        print(f"張った枠: {placed} / {max_slots}（見送り {skipped}）")

    write_outputs(all_records, folds, wf)

    # --- 閾値スキャン: min_is_t を変えたときの未知成績（再シミュレーション不要）---
    scan_thresholds(combos, folds, wf,
                    thresholds=[0.0, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])

    # --- エクイティカーブ＋最大DD（選抜された戦略だけ二次パスで再計算）---
    # 本体プロセスに指標キャッシュを仕込んでから、選抜済み task を再計算する。
    backtest.init_worker(config, ref_cache, target_cache)
    build_and_write_equity(config, wf, all_records, save_dir)

    if not live_records:
        print("選抜条件を満たす戦略がありませんでした（min_is_trades / min_is_t を緩めてください）。")

    print(f"\n{'='*72}")
    print(f" 実運用シグナル")
    print(f"  基準日（データ最終日）: {str(last_date)[:10]}")
    print(f"  選抜: 直近 {train_start}–{max_year} 年で学習 / {wf['select_per']}ごと上位"
          f"{wf['select_top_k']} / min_is_t={wf['min_is_t']}")
    print(f"  選抜された戦略: {len(live_records)} 本")
    print(f"{'='*72}")

    # --- 選抜戦略を emit_open 有効で再計算し、オープン建玉と直近決済を集める ---
    open_rows, recent_rows = [], []
    for rec in live_records:
        task = rec["task"]
        df, _corr, _msg = backtest.calc_trade_results(config, True, *task)
        if df is None or df.empty:
            continue
        pair = f"{task[1]} ← {task[0]}"
        hold_days = task[6]
        if "is_open" not in df.columns:
            df["is_open"] = False
        opens = df[df["is_open"] == True]
        for row in opens.itertuples():
            ed = row.entry_date
            is_pending = bool(getattr(row, "is_pending", False))
            if is_pending:
                # 最終日などに出た新規シグナル。エントリーはまだ（予定日）。
                held = 0
                is_new = True
            else:
                held = int(np.busday_count(np.datetime64(ed, "D"), np.datetime64(last_date, "D")))
                is_new = (str(ed)[:10] == str(last_date)[:10])
            open_rows.append({
                "pair": pair, "position": row.position,
                "signal_date": getattr(row, "signal_date", ""),
                "entry_date": ed, "entry_price": row.entry_price,
                "exit_date": getattr(row, "exit_date", ""),
                "held_days": held, "hold_days": hold_days,
                "remaining": max(hold_days - held, 0),
                "is_new": is_new, "is_pending": is_pending,
                "is_t": rec["is_t"], "is_mean_pct": rec["is_mean_pct"],
            })
        closed = df[df["is_open"] == False].dropna(subset=["exit_date"])
        if not closed.empty:
            for row in closed.sort_values("exit_date").tail(recent_closed).itertuples():
                recent_rows.append({
                    "pair": pair, "position": row.position,
                    "signal_date": getattr(row, "signal_date", ""),
                    "entry_date": row.entry_date, "exit_date": row.exit_date,
                    "profit_pct": row.profit_pct,
                })

    # --- レポート出力 ---
    def arrow(pos):
        return "▲買い" if pos == "long" else "▼売り"

    print("\n■ 現在のオープン建玉／未エントリーの新規シグナル")
    if open_rows:
        open_rows.sort(key=lambda r: (r["is_pending"], r["entry_date"]), reverse=True)
        print(f"  {'銘柄(target←ref)':30s}{'売買':7s}{'シグナル日':12s}{'建玉/予定':11s}"
              f"{'予定決済':11s}{'状態':>10s}  IS_t")
        for r in open_rows:
            status = ("★新規(予定)" if r["is_pending"]
                      else ("★本日建玉" if r["is_new"] else "保有中"))
            print(f"  {r['pair']:30s}{arrow(r['position']):7s}"
                  f"{str(r['signal_date'])[:10]:12s}{str(r['entry_date'])[:10]:11s}"
                  f"{str(r['exit_date'])[:10]:11s}{status:>10s}  {r['is_t']:.2f}")
        pend = [r for r in open_rows if r["is_pending"]]
        if pend:
            print(f"\n  → 未エントリーの新規シグナル（最終日発火）: {len(pend)} 件"
                  f"（シグナル確定済み。上の予定日で建てる）")
        else:
            print(f"\n  → 未エントリーの新規シグナルはなし（既存の保有のみ）")
    else:
        print("  現在オープンの建玉・新規シグナルはありません。")

    print("\n■ 直近の決済済みトレード（参考）")
    if recent_rows:
        recent_rows.sort(key=lambda r: r["exit_date"], reverse=True)
        print(f"  {'銘柄(target←ref)':32s}{'売買':8s}{'決済日':12s}{'損益%':>9s}")
        for r in recent_rows[:15]:
            print(f"  {r['pair']:32s}{arrow(r['position']):8s}"
                  f"{str(r['exit_date'])[:10]:12s}{r['profit_pct']:>+9.3f}")
    else:
        print("  直近の決済トレードがありません。")

    # --- CSV 出力 ---
    live_path = save_dir / "live_signals.csv"
    with open(live_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["type", "pair", "position", "signal_date", "entry_date", "entry_price",
                    "held_days", "remaining_days", "is_new_today", "exit_date",
                    "profit_pct", "is_t", "is_mean_pct"])
        for r in sorted(open_rows, key=lambda x: (x["is_pending"], x["entry_date"]), reverse=True):
            row_type = "PENDING" if r["is_pending"] else "OPEN"
            entry_price = "" if r["is_pending"] else f"{r['entry_price']:.4f}"
            w.writerow([row_type, r["pair"], r["position"], str(r.get("signal_date", ""))[:10],
                        str(r["entry_date"])[:10],
                        entry_price, r["held_days"], r["remaining"],
                        int(r["is_new"]), str(r.get("exit_date", ""))[:10], "",
                        f"{r['is_t']:.4f}", f"{r['is_mean_pct']:.4f}"])
        for r in sorted(recent_rows, key=lambda x: x["exit_date"], reverse=True):
            w.writerow(["CLOSED", r["pair"], r["position"], str(r.get("signal_date", ""))[:10],
                        str(r["entry_date"])[:10],
                        "", "", "", str(r["exit_date"])[:10],
                        f"{r['profit_pct']:.4f}", "", ""])
    print(f"\n出力: {live_path}")
    print("\n※ これは「いまの推奨ポジション」であって、将来の利益を保証するものでは"
          "ありません。実際に張る前に必ず小さいサイズ・紙トレードから。")

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"実験開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"実験終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"総実行時間: {duration}")


if __name__ == "__main__":
    run()
