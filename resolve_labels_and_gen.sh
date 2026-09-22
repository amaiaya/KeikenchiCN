#!/usr/bin/env bash
set -euo pipefail

if ! command -v conda >/dev/null 2>&1; then
    echo "错误：找不到 conda 命令，无法激活 geo 环境。" >&2
    exit 1
fi
CONDA_BASE="$(conda info --base)"
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate geo

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"

shopt -s nullglob
loca_files=(fwss_reader/loca_*_wgs.csv)
if (( ${#loca_files[@]} != 1 )); then
    echo "错误：期望 fwss_reader 中有且只有一个 loca_*_wgs.csv，实际找到 ${#loca_files[@]} 个。" >&2
    echo "请先运行 ./update_fwss_and_gen.sh。" >&2
    exit 1
fi

loca_file="${loca_files[0]}"
date="${loca_file##*/loca_}"
date="${date%_wgs.csv}"

echo "[1/3] 根据 add_labels/add_label_list.json 生成 ${date} 的 fullname 标签 JSON..."
"$PYTHON_BIN" add_labels/resolve_full_names.py --date "$date"

echo "[2/3] 生成 ${date} 的最终地图、统计和带标签县区 CSV..."
"$PYTHON_BIN" gen_vis_keikenchi_map.py --date "$date"

history_dir="history"
result_file="经过县区名_base-WGS_path-WGS.csv"
history_file="${history_dir}/经过县区名_base-WGS_path-WGS_${date}.csv"
mkdir -p "$history_dir"

echo "[3/3] 备份带标签县区 CSV 到 ${history_file}..."
cp -- "$result_file" "$history_file"

echo
echo "完成：${date} 的最终结果已生成，历史备份为 ${history_file}。"
