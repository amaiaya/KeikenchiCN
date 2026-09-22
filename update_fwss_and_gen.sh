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

echo "[1/2] 读取最新 FWSS，并只保留最新 loca CSV..."
"$PYTHON_BIN" fwss_reader/fwss_reader.py

shopt -s nullglob
loca_files=(fwss_reader/loca_*_wgs.csv)
if (( ${#loca_files[@]} != 1 )); then
    echo "错误：期望 fwss_reader 中有且只有一个 loca_*_wgs.csv，实际找到 ${#loca_files[@]} 个。" >&2
    exit 1
fi

loca_file="${loca_files[0]}"
date="${loca_file##*/loca_}"
date="${date%_wgs.csv}"

echo "[2/2] 生成 ${date} 的无标签县区 CSV..."
"$PYTHON_BIN" gen_vis_keikenchi_map.py --date "$date" --no-labels

echo
echo "完成。请手动修改 add_labels/add_label_list.json，然后运行："
echo "  ./resolve_labels_and_gen.sh"
