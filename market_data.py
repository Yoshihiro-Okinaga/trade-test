import pandas as pd
from pathlib import Path

from backtest_config import BackTestConfig, SignalType


# ワーカープロセスごとに、読み込み済みのCSVデータを保持する
DATA_CACHE = {}

DATA_FOLDER = Path(__file__).resolve().parent / "stock-data" / "Manual"
REQUIRED_COLUMNS = ["日付", "終値", "高値", "安値"]


class MarketData:
    def __init__(self, path: str):
        self.path = path
        self.df = self.load_data(path)
        self.ref = None
        self.target = None


    # === データ読み込み ===
    def load_data(self, path):
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


    def calc_target_prices(self, hold_days):
        """売買対象としての決済価格を計算して返す。hold_days にだけ依存する。"""
        target = self.df.copy()
        target["target_base"] = target["終値"]
        target["target_exit"] = target["target_base"].shift(-hold_days)
        target["exit_date"] = target["日付"].shift(-hold_days)
        target["target_change"] = target["target_exit"] - target["target_base"]
        target["target_change_pct"] = target["target_change"] / target["target_base"] * 100
        self.target = target
        return target


    def calc_ref_signals(self, ref_lag_days, start_days, sma_period):
        """シグナル源としての指標を計算して返す。
        依存するのは ref_lag_days / start_days / sma_period の3つだけ。
        閾値や counter_trade は売買判定で使うもので、ここでは使わない。"""
        ref = self.df.copy()

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

        self.ref = ref
        return ref


def build_caches(config):
    """必要な指標を、パラメータの組み合わせぶんだけ事前に計算する。

    指標は銘柄だけでなくパラメータにも依存するので、キーにパラメータを含める。
    銘柄名だけをキーにすると、別のパラメータで計算した結果を誤って使い回して
    しまうため注意。

    タスクごとに計算し直すと同じ計算を何万回も繰り返すことになるが、
    実際に必要な組み合わせは
      ref    : 銘柄 × ref_lag_days × start_days × sma_period
      target : 銘柄 × hold_days
    だけなので、ここでまとめて作っておけば済む。
    """
    ref_cache = {}
    target_cache = {}
    ref_set = set(config.ref_list)
    target_set = set(config.target_list)
    # ref と target で必要な銘柄が異なりうる（symbol_pairs 指定時など）。
    # union を1回ずつ MarketData 化し、ref_cache は ref_list、
    # target_cache は target_list から作る。総当たり時は target_list ⊆ ref_list
    # なので、作られるキーは従来の必要ぶんと一致し、出力は変わらない。
    all_names = list(dict.fromkeys(list(config.ref_list) + list(config.target_list)))
    for name in all_names:
        data = MarketData(name)
        if name in ref_set:
            for ref_lag_days in config.ref_lag_days_list:
                for start_days in config.start_days_list:
                    for sma_period in config.sma_period_list:
                        key = (name, ref_lag_days, start_days, sma_period)
                        ref_cache[key] = data.calc_ref_signals(ref_lag_days, start_days, sma_period)
        if name in target_set:
            for hold_days in config.hold_days_list:
                target_cache[(name, hold_days)] = data.calc_target_prices(hold_days)
    return ref_cache, target_cache
