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
    「年ごとの十分統計量 (件数, 合計, 二乗和, 勝ち数)」に畳んで持ち帰る。
    フォールドの区切りは年境界なので、あとはこの年別統計を学習/検証ウィンドウで
    足し合わせるだけで、再シミュレーションなしに選抜と評価ができる。

制約・注意:
    - フォールドは年単位で区切る（トレードは「エントリー年」で各年に割り当てる）。
    - use_excess_return=true のドリフト（相場方向の除去量）は、元コードでは全期間平均
      で計算される。厳密な leak-free を求めるなら use_excess_return=[false] で回すこと。
      本モジュールはそれ以外の未来情報の混入は排除している。
    - signal_type に "Test"（インサンプル相関で指標を選ぶ）が含まれると、その選択自体が
      全期間 leak になるため walk-forward の前提が崩れる。含まれていれば警告する。
    - t値は各トレードを独立とみなす近似（トレード間・銘柄間の相関は補正しない）。
      main.py と同じ前提なので、相対比較の目安として使うこと。

使い方:
    config.toml に [walkforward] セクションを足してから、
        python walkforward.py
    出力:
        walkforward_selection.csv  … 各フォールドで何を選び、検証期間でどうだったか
        walkforward_summary.csv    … フォールド別＋全体の未知期間成績
        walkforward_equity.csv     … 未知トレードを実現日順に連結した累積リターン
    コンソール: 残存率・未知成績・閾値スキャン・最大ドローダウン
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
SAVE_PATH = "./"#"../trade-test/"

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


def agg_years(year_stats, lo, hi):
    """年別統計 {year: (n, sum, sumsq, wins)} を [lo, hi] 年で合算する。"""
    n = s = ss = w = 0
    for year, (c, su, sq, wi) in year_stats.items():
        if lo <= year <= hi:
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


def score_of(metric, n, s, ss):
    """選抜スコアを返す。metric: 't_value' / 'average_pct' / 'total_pct'。"""
    mean, std, t = mean_std_t(n, s, ss)
    if metric == "t_value":
        return t
    if metric == "average_pct":
        return mean
    if metric == "total_pct":
        return float(s)
    raise ValueError(f"未知の select_metric: {metric!r}")


def select_for_fold(combos, fold, metric, select_per, top_k, min_is_trades,
                    min_is_t=0.0):
    """1フォールドぶんの選抜と未知期間評価を行い、選ばれた戦略の記録を返す。

    combos: [{"task": (...), "target": name, "years": {year:(n,s,ss,w)}}, ...]
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
        n, s, ss, w = agg_years(combo["years"], train_start, train_end)
        if n < min_is_trades:
            continue
        # 品質ゲート: 学習期間の t値が基準に満たない候補は捨てる。
        # min_is_t=0.0 のときは何も捨てず従来の挙動を保つ（NaN t を巻き込まない）。
        if min_is_t > 0.0:
            _, _, is_t = mean_std_t(n, s, ss)
            if math.isnan(is_t) or is_t < min_is_t:
                continue
        score = score_of(metric, n, s, ss)
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
        oos_n, oos_s, oos_ss, oos_w = agg_years(combo["years"], test_start, test_end)
        oos_mean = (oos_s / oos_n) if oos_n > 0 else float("nan")
        records.append({
            "train_start": train_start, "train_end": train_end,
            "test_start": test_start, "test_end": test_end,
            "task": combo["task"], "target": combo["target"],
            "is_trades": is_n, "is_mean_pct": is_mean, "is_t": is_t,
            "oos_trades": oos_n, "oos_sum": oos_s, "oos_sumsq": oos_ss,
            "oos_wins": oos_w, "oos_mean_pct": oos_mean,
        })
    return records


# ============================================================================
# シミュレーション本体の再利用（重い依存はここで import）
# ============================================================================

def collect_year_stats(task):
    """ワーカー実行単位。1つのパラメータ組み合わせについて全履歴のトレードを計算し、
    損益率(profit_pct)を年別の十分統計量に畳んで返す。
    config と指標キャッシュは backtest.init_worker が仕込んだグローバルを使う。"""
    import backtest  # ワーカー側で解決

    config = backtest._WORKER_CONFIG
    df, _corr, _msg = backtest.calc_trade_results(config, *task)
    if df is None or df.empty:
        return None

    year_stats = {}
    # groupby は速いが、ここでは numpy で軽く回す
    years = df["year"].to_numpy()
    pct = df["profit_pct"].to_numpy()
    for y, p in zip(years, pct):
        y = int(y)
        c, s, ss, w = year_stats.get(y, (0, 0.0, 0.0, 0))
        year_stats[y] = (c + 1, s + float(p), ss + float(p) * float(p), w + (1 if p > 0 else 0))

    return {"task": tuple(task), "target": task[1], "years": year_stats}


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
    戻り値 (max_dd, peak_idx, trough_idx)。max_dd は下落幅で常に非負。"""
    peak = float("-inf")
    cur_peak_i = 0
    max_dd = 0.0
    mdd_peak = mdd_trough = 0
    for i, v in enumerate(cumulative):
        if v > peak:
            peak = v
            cur_peak_i = i
        dd = peak - v
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
    curve = []
    for t in ordered:
        cum += t["profit_pct"]
        row = dict(t)
        row["cumulative_pct"] = cum
        curve.append(row)
    cumulative = [row["cumulative_pct"] for row in curve]
    if cumulative:
        mdd, pk, tr = max_drawdown(cumulative)
        final = cumulative[-1]
    else:
        mdd, pk, tr, final = 0.0, 0, 0, 0.0
    return curve, {"final_pct": final, "max_dd_pct": mdd,
                   "peak_idx": pk, "trough_idx": tr, "n": len(curve)}


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
        df, _corr, _msg = backtest.calc_trade_results(config, *task)
        if df is None or df.empty:
            continue
        pair = f"{task[1]} ← {task[0]}"
        for r in recs:
            ts, te = r["test_start"], r["test_end"]
            # 選抜と同じ「エントリー年」基準で検証期間を切り出す
            sub = df[(df["year"] >= ts) & (df["year"] <= te)]
            for row in sub.itertuples():
                trades.append({
                    "exit_date": row.exit_date,
                    "entry_date": row.entry_date,
                    "profit_pct": float(row.profit_pct),
                    "pair": pair,
                    "test_period": f"{ts}-{te}",
                })
    return trades


def build_and_write_equity(config, records):
    try:
        trades = collect_oos_trades(config, records)
    except Exception as e:
        print(f"\nエクイティ計算をスキップしました（{e}）")
        return
    if not trades:
        print("\nエクイティ: 未知トレードが取得できませんでした。")
        return

    curve, stats = build_equity(trades)
    eq_path = SAVE_PATH + "walkforward_equity.csv"
    with open(eq_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["exit_date", "profit_pct", "cumulative_pct", "pair", "test_period"])
        for row in curve:
            w.writerow([str(row["exit_date"])[:10], f"{row['profit_pct']:.6f}",
                        f"{row['cumulative_pct']:.6f}", row["pair"], row["test_period"]])

    n = stats["n"]
    print("\n=== エクイティ（未知トレードを実現日で連結。等額・非複利＝1取引1単位を加算）===")
    print(f"未知トレード数       : {n:,}")
    print(f"累積リターン（合計%） : {stats['final_pct']:+.2f}%")
    print(f"1取引あたり平均       : {stats['final_pct'] / n:+.4f}%")
    print(f"最大ドローダウン      : {stats['max_dd_pct']:.2f}%（累積%ポイント）")
    if stats["max_dd_pct"] > 0:
        pk = curve[stats["peak_idx"]]
        tr = curve[stats["trough_idx"]]
        print(f"  DD区間: {str(pk['exit_date'])[:10]}（山 {pk['cumulative_pct']:+.1f}%）"
              f" → {str(tr['exit_date'])[:10]}（谷 {tr['cumulative_pct']:+.1f}%）")
    print(f"出力: {eq_path}")


def write_outputs(records, folds, wf):
    # 1) 選抜の明細（フォールドごとに何を選び、未知期間でどうだったか）
    sel_path = SAVE_PATH + "walkforward_selection.csv"
    with open(sel_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "test_start", "test_end", "train_start", "train_end",
            "target", "ref", "signal_type", "counter_trade", "use_excess_return",
            "threshold_width", "hold_days", "start_days", "sma_period",
            "is_trades", "is_mean_pct", "is_t", "oos_trades", "oos_mean_pct",
        ])
        for r in sorted(records, key=lambda x: (x["test_start"], x["target"])):
            ref, target, sig, counter, excess, width, hold, start, sma = r["task"]
            writer.writerow([
                r["test_start"], r["test_end"], r["train_start"], r["train_end"],
                target, ref, sig, counter, excess, width, hold, start, sma,
                r["is_trades"], f"{r['is_mean_pct']:.9f}",
                ("" if math.isnan(r["is_t"]) else f"{r['is_t']:.9f}"),
                r["oos_trades"],
                ("" if r["oos_trades"] == 0 else f"{r['oos_mean_pct']:.9f}"),
            ])

    # 2) フォールド別＋全体の未知期間サマリ
    per_fold = {}
    for r in records:
        key = (r["test_start"], r["test_end"])
        n, s, ss, w = per_fold.get(key, (0, 0.0, 0.0, 0))
        per_fold[key] = (n + r["oos_trades"], s + r["oos_sum"],
                         ss + r["oos_sumsq"], w + r["oos_wins"])

    sum_path = SAVE_PATH + "walkforward_summary.csv"
    with open(sum_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["test_start", "test_end", "oos_trades",
                         "oos_mean_pct", "oos_t", "oos_win_rate"])
        for (ts, te) in sorted(per_fold):
            n, s, ss, w = per_fold[(ts, te)]
            mean, std, t = mean_std_t(n, s, ss)
            win = (w / n * 100) if n else float("nan")
            writer.writerow([ts, te, n, f"{mean:.9f}",
                             ("" if math.isnan(t) else f"{t:.9f}"), f"{win:.4f}"])

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
    print(f"\n出力: {sel_path} / {sum_path}")


def run():
    import tomllib
    import backtest
    import market_data
    import backtest_config

    start_time = datetime.datetime.now()

    config_path = Path(__file__).parent / "config.toml"
    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
    except FileNotFoundError:
        print(f"エラー: {config_path} が見つかりません。")
        sys.exit(1)

    config = backtest_config.BackTestConfig(config_data)
    wf = read_wf_params(config_data)

    # 前提が崩れるケースを先に知らせる
    if "Test" in config.signal_type_list:
        print("警告: signal_type に 'Test' が含まれています。'Test' は全期間の相関で"
              "指標を選ぶため、walk-forward の前提（未来を見ない）が崩れます。")
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
    ref_cache, target_cache = market_data.build_caches(config)
    print(f"事前計算 完了（ref {len(ref_cache)} 件 / target {len(target_cache)} 件）")

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
                executor.map(collect_year_stats, tasks, chunksize=chunksize), start=1
            ):
                if result is not None:
                    combos.append(result)
                print(f"\r集計: {done}/{total}", end="", flush=True)
    else:
        backtest.init_worker(config, ref_cache, target_cache)
        for done, task in enumerate(tasks, start=1):
            result = collect_year_stats(task)
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
        all_years.update(combo["years"].keys())
    min_year, max_year = min(all_years), max(all_years)
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
    build_and_write_equity(config, all_records)

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"実験開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"実験終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"総実行時間: {duration}")


if __name__ == "__main__":
    run()
