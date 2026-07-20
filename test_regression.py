"""
回帰テスト（ゴールデンファイル方式）

リファクタリングの前後で backtest の出力が変わっていないことを確認する。
「正解」として保存しておいた CSV（ゴールデン）と、いまのコードが出力した
CSV を比較し、実質的に同じなら PASS、違えば違う箇所を表示して FAIL する。

数値列は浮動小数点のごくわずかな揺れ（環境差・pandas バージョン差）を
許容するため np.isclose で比較する。文字列列と行の順序・行数・列構成は
完全一致を要求する。

使い方:
    # まず「正解」を1回作る（信頼できる状態のコードで実行）
    python main.py                       # trade_ranking.csv などを生成
    cp trade_ranking.csv golden.csv      # それをゴールデンとして保存

    # 以降、リファクタリングのたびに:
    python main.py                       # 新しい出力を生成
    python test_regression.py golden.csv trade_ranking.csv

    # 一致すれば "PASS"、違えば違う行・列を表示して "FAIL"
"""
import sys
import numpy as np
import pandas as pd

# 数値比較の許容誤差。ROUND_DIGITS=9 で出力しているので、
# それより十分小さい絶対誤差を許容する。相対誤差も併用する。
ABS_TOL = 1e-6
REL_TOL = 1e-9

# 文字列として扱う（完全一致を要求する）列
STRING_COLUMNS = ["target", "ref", "signal_type"]


def load(path):
    # correlation などが空欄（NaN）になる行があるので、そのまま読み込む。
    # signal_type などの文字列列は文字列として読む。
    return pd.read_csv(path)


def compare(golden_path, actual_path):
    golden = load(golden_path)
    actual = load(actual_path)

    problems = []

    # 1. 列の構成が同じか
    if list(golden.columns) != list(actual.columns):
        problems.append(
            f"列構成が違います。\n  golden: {list(golden.columns)}\n  actual: {list(actual.columns)}"
        )
        # 列が違うと以降の比較が無意味なので、ここで打ち切る
        return problems

    # 2. 行数が同じか
    if len(golden) != len(actual):
        problems.append(f"行数が違います。golden={len(golden)} 行, actual={len(actual)} 行")
        # 行数が違っても、可能な範囲で先頭を比較したいので続行はしない
        return problems

    # 3. 各列を比較
    for col in golden.columns:
        g = golden[col]
        a = actual[col]

        if col in STRING_COLUMNS or g.dtype == object:
            # 文字列列: 完全一致（NaN 同士は一致とみなす）
            mismatch = ~((g == a) | (g.isna() & a.isna()))
            if mismatch.any():
                idx = mismatch[mismatch].index[:5]  # 最初の5件だけ表示
                detail = "\n".join(
                    f"    行{i}: golden={g[i]!r} actual={a[i]!r}" for i in idx
                )
                problems.append(f"列 '{col}' に文字列の不一致 {mismatch.sum()} 件:\n{detail}")
        else:
            # 数値列: NaN の位置が一致し、かつ数値が近いこと
            g_num = pd.to_numeric(g, errors="coerce")
            a_num = pd.to_numeric(a, errors="coerce")

            # NaN の位置が食い違っていないか
            nan_mismatch = g_num.isna() != a_num.isna()
            if nan_mismatch.any():
                idx = nan_mismatch[nan_mismatch].index[:5]
                detail = "\n".join(
                    f"    行{i}: golden={g[i]!r} actual={a[i]!r}" for i in idx
                )
                problems.append(f"列 '{col}' で NaN の位置がずれています {nan_mismatch.sum()} 件:\n{detail}")

            # 両方が数値の行だけ、近さを確認
            both = ~g_num.isna() & ~a_num.isna()
            close = np.isclose(g_num[both], a_num[both], rtol=REL_TOL, atol=ABS_TOL)
            if not close.all():
                bad_idx = both[both].index[~close][:5]
                detail = "\n".join(
                    f"    行{i}: golden={g_num[i]:.12g} actual={a_num[i]:.12g} "
                    f"(差={abs(g_num[i]-a_num[i]):.3g})"
                    for i in bad_idx
                )
                problems.append(
                    f"列 '{col}' に数値の不一致 {(~close).sum()} 件（許容誤差 abs={ABS_TOL}, rel={REL_TOL}）:\n{detail}"
                )

    return problems


def main():
    if len(sys.argv) != 3:
        print("使い方: python test_regression.py <golden.csv> <actual.csv>")
        sys.exit(2)

    golden_path, actual_path = sys.argv[1], sys.argv[2]
    problems = compare(golden_path, actual_path)

    if not problems:
        print("PASS: 出力はゴールデンと一致しています。")
        sys.exit(0)
    else:
        print("FAIL: 出力がゴールデンと違います。\n")
        for p in problems:
            print("- " + p)
        print(f"\n合計 {len(problems)} 種類の不一致が見つかりました。")
        sys.exit(1)


if __name__ == "__main__":
    main()
