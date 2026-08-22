from dataclasses import dataclass

from walkforward_config import WalkForwardMode


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def make_folds(
    min_year: int,
    max_year: int,
    train_years: int,
    test_years: int,
    step_years: int,
    mode: WalkForwardMode,
) -> list[WalkForwardFold]:
    """年境界で Walk-forward のフォールドを作る。

    最初の検証期間は「初期学習期間ぶん」だけ後ろから始まる。
    step_years=test_years にすると検証期間が重ならずに時間軸を敷き詰める
    （＝各未知トレードが1回だけ数えられる）。
    mode="anchored" は学習開始を min_year に固定して期間を伸ばす。
    mode="rolling" は学習期間を固定長でスライドさせる。
    """
    if train_years < 1 or test_years < 1 or step_years < 1:
        raise ValueError(
            "train_years / test_years / step_years は1以上にしてください。"
        )

    folds = []
    test_start = min_year + train_years

    while test_start + test_years - 1 <= max_year:
        test_end = test_start + test_years - 1
        train_end = test_start - 1

        if mode == WalkForwardMode.ANCHORED:
            train_start = min_year
        elif mode == WalkForwardMode.ROLLING:
            train_start = test_start - train_years
        else:
            raise ValueError(
                f"mode は 'anchored' か 'rolling'。指定値: {mode!r}"
            )

        folds.append(
            WalkForwardFold(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        test_start += step_years

    return folds
