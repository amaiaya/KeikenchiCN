#!/usr/bin/env python3
"""更新 FWSS，比较新增区县，并等待用户确认后生成最终结果。"""

import csv
import re
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
CURRENT_CSV = PROJECT_DIR / "经过县区名_base-WGS_path-WGS.csv"
HISTORY_DIR = PROJECT_DIR / "history"
FIRST_SCRIPT = PROJECT_DIR / "update_fwss_and_gen.sh"
SECOND_SCRIPT = PROJECT_DIR / "resolve_labels_and_gen.sh"
HISTORY_PATTERN = re.compile(r"经过县区名_base-WGS_path-WGS_(20\d{6})\.csv$")


def read_region_names(csv_path):
    """读取 CSV 中的区县名称，忽略 count 和 label。"""
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or "name" not in reader.fieldnames:
            raise ValueError(f"CSV 缺少 name 列: {csv_path}")
        return {
            row["name"].strip()
            for row in reader
            if row.get("name") and row["name"].strip()
        }


def find_previous_csv():
    """优先使用当前结果，否则使用 history 中日期最新的备份。"""
    if CURRENT_CSV.exists():
        return CURRENT_CSV

    history_files = []
    for path in HISTORY_DIR.glob("经过县区名_base-WGS_path-WGS_*.csv"):
        match = HISTORY_PATTERN.fullmatch(path.name)
        if match:
            history_files.append((match.group(1), path))
    if history_files:
        return max(history_files, key=lambda item: item[0])[1]
    return None


def run_script(script_path):
    """在项目根目录运行已有 shell 脚本，并保留实时输出。"""
    subprocess.run(["bash", str(script_path)], cwd=PROJECT_DIR, check=True)


def main():
    previous_csv = find_previous_csv()
    previous_names = read_region_names(previous_csv) if previous_csv else set()

    print("=== 第一步：更新 FWSS 并生成无标签 CSV ===")
    run_script(FIRST_SCRIPT)

    if not CURRENT_CSV.exists():
        raise FileNotFoundError(f"未生成无标签 CSV: {CURRENT_CSV}")
    current_names = read_region_names(CURRENT_CSV)
    added_names = sorted(current_names - previous_names)

    print()
    if previous_csv:
        print(f"比较基准: {previous_csv.relative_to(PROJECT_DIR)}")
    else:
        print("比较基准: 没有找到上一个 CSV，本次所有区县都视为新增。")
    print(f"上一个 CSV 区县数: {len(previous_names)}")
    print(f"最新无标签 CSV 区县数: {len(current_names)}")
    print(f"新增区县数: {len(added_names)}")

    if added_names:
        print("新增区县：")
        for name in added_names:
            print(f"  {name}")
    else:
        print("没有新增区县。")

    print()
    print("如需修改 add_labels/add_label_list.json，请现在完成修改。")
    print("修改完成或无需修改后，按回车继续；输入 q 并回车则中止后续生成。")
    try:
        answer = input("> ").strip().lower()
    except EOFError:
        print("未收到确认输入，已中止后续生成。")
        return 1

    if answer == "q":
        print("已中止，未生成带标签结果。")
        return 0

    print()
    print("=== 第二步：解析标签并生成最终结果 ===")
    run_script(SECOND_SCRIPT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
