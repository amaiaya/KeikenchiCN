#!/bin/bash

TAIWAN_DIR="$(dirname "$0")/taiwan"
TARGET="$(dirname "$0")/ok_geo_gcj.csv"

for csv in "$TAIWAN_DIR"/taiwan_boundaries_gcj.csv; do
    # 跳过第一行（表头），追加剩余内容
    tail -n +2 "$csv" >> "$TARGET"
    echo "Appended: $csv"
done
