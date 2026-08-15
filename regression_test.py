from pathlib import Path

import main
import walkforward


PROJECT_DIR = Path(__file__).resolve().parent
TEST_RESULT_BASE_DIR = (PROJECT_DIR / "../TestResult").resolve()
#TEST_RESULT_DIR = (TEST_RESULT_BASE_DIR / "stock_electric").resolve()
TEST_RESULT_DIR = TEST_RESULT_BASE_DIR
TEST_CONFIG_PATH = TEST_RESULT_DIR / "config.toml"
TEST_DATA_FOLDER = TEST_RESULT_BASE_DIR / "stock-data" / "Manual"

# live_signals.csv は最後に実行した指標で上書きされる。
# 現在の config.toml と同じ t_value を最後にして、通常実行時の結果と揃える。
WALKFORWARD_METRICS = [
    "lower_confidence_bound",
    "year_t_value",
    "t_value",
]


def validate_test_environment():
    """回帰テストに必要な固定データが揃っていることを確認する。"""
    required_paths = [
        TEST_RESULT_DIR,
        TEST_CONFIG_PATH,
        TEST_DATA_FOLDER,
    ]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing_text = "\n".join(f"  {path}" for path in missing_paths)
        raise FileNotFoundError(
            "回帰テストに必要なファイルまたはフォルダがありません:\n"
            f"{missing_text}"
        )


def run_regression_test():
    """固定入力から主要CSVを再生成する。差分の判定はGitに任せる。"""
    validate_test_environment()

    print("=== 回帰テスト: trade ranking ===")
    main.main(
        config_path=TEST_CONFIG_PATH,
        data_folder=TEST_DATA_FOLDER,
        save_dir=TEST_RESULT_DIR,
    )

    for metric in WALKFORWARD_METRICS:
        print(f"\n=== 回帰テスト: walk-forward ({metric}) ===")
        walkforward.run(
            config_path=TEST_CONFIG_PATH,
            data_folder=TEST_DATA_FOLDER,
            save_dir=TEST_RESULT_DIR,
            select_metric=metric,
        )

    print("\n=== 回帰テスト完了 ===")
    print(f"結果は {TEST_RESULT_DIR} に上書きしました。")
    print("変更の有無は Git の差分で確認してください。")


if __name__ == "__main__":
    run_regression_test()
