import pandas as pd
import glob
import os
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# CSVフォルダ（サブフォルダも検索）
CSV_FOLDER = "./stock-data/FXCFD/"

# diff_days（騰落の期間）を範囲指定
# 例：1〜5日騰落を調べる
diff_day_list = range(1, 6)

# lag_days（B銘柄を何日前にずらすか）を範囲指定
# 今回は偶然相関を減らすため、1〜10日までにする
lag_day_list = range(1, 11)

# True の場合、lag_days >= diff_days の組み合わせだけ計算する
# これにより、同一銘柄で騰落期間が重なる組み合わせを避ける
USE_ONLY_NON_OVERLAPPING_LAG = True

# 並列数
# 大きくしすぎるとメモリ使用量が増えるため、まずは4程度が無難。
MAX_WORKERS = min(4, os.cpu_count() or 1)

# 出力ファイル
OUTPUT_TOP100_OVERALL = "top100_diff_lagged_correlation_overall.csv"
OUTPUT_TOP20_CROSS_ASSET = "top20_cross_asset_correlation.csv"
OUTPUT_TOP20_SELF_ASSET = "top20_self_asset_correlation.csv"


def load_close_series_dict(csv_folder):
    """CSVフォルダから各銘柄の終値Seriesを読み込む。"""
    csv_files = glob.glob(os.path.join(csv_folder, "**", "*.csv"), recursive=True)

    data_dict = {}

    for file in csv_files:
        name = os.path.splitext(os.path.basename(file))[0]
        df = pd.read_csv(file)

        # 列名の空白・不可視文字を除去
        df.columns = df.columns.str.strip()

        # 日付を datetime に変換
        df["日付"] = pd.to_datetime(df["日付"], errors="coerce")

        # 日付に変換できなかった行を除外し、古い日付から順に並べる
        df = df.dropna(subset=["日付"])
        df = df.sort_values("日付")
        df = df.set_index("日付")

        # 終値列を自動検出（"終値" を含む列）
        close_col = [c for c in df.columns if "終値" in c]
        if len(close_col) == 0:
            print(f"⚠ 終値列が見つかりません: {file}")
            continue

        close_col = close_col[0]

        # 終値を保存
        data_dict[name] = df[close_col]

    return data_dict


def make_diff_dict(data_dict, diff_days):
    """
    各銘柄の diff_days 日騰落を計算する。

    元コードと同じく、各Seriesごとに diff() を計算する。
    """
    diff_dict = {}

    for name, series in data_dict.items():
        diff_dict[name] = series.diff(diff_days)

    return diff_dict


def make_a_dataframe(diff_dict, names):
    """
    A側の騰落DataFrameを作る。

    A側は lag_days が変わっても同じなので、
    diff_days ごとに1回だけ作る。
    """
    a_df = pd.concat(diff_dict, axis=1, sort=True)

    a_columns = [f"A__{name}" for name in names]
    a_df.columns = a_columns

    return a_df, a_columns


def make_shifted_dict(diff_dict, lag_days):
    """
    B銘柄側の騰落を lag_days 日ずらす。

    元コードと同じく、各Seriesごとに shift() を計算する。
    """
    shifted_dict = {}

    for name, series in diff_dict.items():
        shifted_dict[name] = series.shift(lag_days)

    return shifted_dict


def make_b_dataframe(shifted_dict, names):
    """B側の騰落DataFrameを作る。"""
    b_df = pd.concat(shifted_dict, axis=1, sort=True)

    b_columns = [f"B__{name}" for name in names]
    b_df.columns = b_columns

    return b_df, b_columns


def calculate_lagged_correlation(
    a_df,
    a_columns,
    diff_dict,
    names,
    diff_days,
    lag_days,
):
    """
    Aの騰落と、lag_daysずらしたBの騰落の相関を一括計算する。

    元コードでは A, B のペアごとに pd.concat() と corr() を呼んでいた。
    ここでは全銘柄をDataFrameにまとめて、相関行列から A × B 部分だけを取り出す。
    """
    shifted_dict = make_shifted_dict(diff_dict, lag_days)
    b_df, b_columns = make_b_dataframe(shifted_dict, names)

    combined_df = pd.concat([a_df, b_df], axis=1, sort=True)

    corr_matrix = combined_df.corr()

    corr_block = corr_matrix.loc[a_columns, b_columns]
    corr_values = corr_block.to_numpy()

    pair_count = len(names) * len(names)

    corr_df = pd.DataFrame({
        "A": np.repeat(names, len(names)),
        "B": np.tile(names, len(names)),
        "diff_days": diff_days,
        "lag_days": lag_days,
        "corr": corr_values.reshape(pair_count),
    })

    corr_df["abs_corr"] = corr_df["corr"].abs()

    return corr_df


def get_lag_days_for_diff_days(diff_days):
    """
    diff_days に対して、実際に計算する lag_days 一覧を返す。

    USE_ONLY_NON_OVERLAPPING_LAG=True の場合、
    lag_days >= diff_days のものだけを対象にする。
    """
    if not USE_ONLY_NON_OVERLAPPING_LAG:
        return list(lag_day_list)

    return [
        lag_days
        for lag_days in lag_day_list
        if lag_days >= diff_days
    ]


def calculate_one_diff_days(data_dict, names, diff_days):
    """
    1つの diff_days に対して、複数の lag_days を並列計算する。
    """
    # diff_days 日騰落を計算
    diff_dict = make_diff_dict(data_dict, diff_days)

    # A側は lag_days が変わっても同じなので、ここで1回だけ作る
    a_df, a_columns = make_a_dataframe(diff_dict, names)

    target_lag_day_list = get_lag_days_for_diff_days(diff_days)

    all_corr_df_list = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []

        for lag_days in target_lag_day_list:
            future = executor.submit(
                calculate_lagged_correlation,
                a_df,
                a_columns,
                diff_dict,
                names,
                diff_days,
                lag_days,
            )
            futures.append(future)

        # futures は target_lag_day_list の順番で入っている。
        # 同じ順番で result() を取り出すことで、元コードに近い順序を維持する。
        for future in futures:
            corr_df = future.result()
            all_corr_df_list.append(corr_df)

    return all_corr_df_list


def save_ranking_files(all_corr_df):
    """
    ランキングを用途別に保存する。

    1. 全体トップ100
    2. 他銘柄ペア A != B のトップ20
    3. 自己ペア A == B のトップ20
    """
    ranked_df = all_corr_df.sort_values("abs_corr", ascending=False)

    top100_overall = ranked_df.head(100)

    cross_asset_df = ranked_df[ranked_df["A"] != ranked_df["B"]]
    self_asset_df = ranked_df[ranked_df["A"] == ranked_df["B"]]

    top20_cross_asset = cross_asset_df.head(20)
    top20_self_asset = self_asset_df.head(20)

    print("=== 全体トップ100のうち上位20 ===")
    print(top100_overall.head(20))

    print()
    print("=== 他銘柄トップ20（A != B） ===")
    print(top20_cross_asset)

    print()
    print("=== 自己ペアトップ20（A == B） ===")
    print(top20_self_asset)

    # BOMなし UTF-8 で保存
    top100_overall.to_csv(
        OUTPUT_TOP100_OVERALL,
        encoding="utf-8",
        index=False,
    )

    top20_cross_asset.to_csv(
        OUTPUT_TOP20_CROSS_ASSET,
        encoding="utf-8",
        index=False,
    )

    top20_self_asset.to_csv(
        OUTPUT_TOP20_SELF_ASSET,
        encoding="utf-8",
        index=False,
    )


def main():
    data_dict = load_close_series_dict(CSV_FOLDER)

    # 銘柄名一覧
    names = list(data_dict.keys())

    print(f"銘柄数: {len(names)}")
    print(f"並列数: {MAX_WORKERS}")
    print(f"lag_days >= diff_days のみ: {USE_ONLY_NON_OVERLAPPING_LAG}")
    print(f"lag_days 範囲: {list(lag_day_list)}")

    # 全 diff_days × lag_days の結果をまとめるリスト
    all_corr_df_list = []

    for diff_days in diff_day_list:
        target_lag_day_list = get_lag_days_for_diff_days(diff_days)

        print(
            f"diff_days = {diff_days} を計算中..."
            f" lag_days = {list(target_lag_day_list)}"
        )

        corr_df_list = calculate_one_diff_days(
            data_dict=data_dict,
            names=names,
            diff_days=diff_days,
        )

        all_corr_df_list.extend(corr_df_list)

    # DataFrame化
    all_corr_df = pd.concat(all_corr_df_list, ignore_index=True)

    save_ranking_files(all_corr_df)


if __name__ == "__main__":
    main()
