#!/bin/bash
#
# @Author      : Amai Aya
# @Date        : 2026-06-22 19:54:03 CST
# @Modified    : 2026-06-22 19:54:03 CST
# @Version     : 1.0
# @Description : 


#!/bin/bash

# countries=("Kazakhstan" "Kyrgyzstan" "Tajikistan" "Turkmenistan" "Uzbekistan")
# Kyrgyzstan 和 Turkmenistan数据不对

# countries=("Kazakhstan" "Tajikistan" "Uzbekistan")
# for country in "${countries[@]}"; do
#     python extract_OSM.py "$country" --level1 4 --level2 6
#     python gen_csv_and_vis.py ${country}_admin2.geojson
# done

countries=("Russia")
for country in "${countries[@]}"; do
    python extract_OSM.py "$country" --level1 4 --level2 6
    python gen_csv_and_vis.py ${country}_admin2.geojson
done
