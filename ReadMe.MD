# 展示
![Keikenchi Map at 2026-06-19.](./县级可视化_base-WGS_path-WGS.jpg)

# 使用流程

在项目根目录执行以下命令。两个流程脚本会自动执行 `conda activate geo`；`fwss_reader.py` 不带参数时会选择 `fwss/` 中时间戳最新的快照，只保留最新的 `loca_YYYYMMDD_wgs.csv`。

日常更新 FWSS 时，可以直接使用两个脚本：

```bash
./update_fwss_and_gen.sh
# 手动修改 add_labels/add_label_list.json
./resolve_labels_and_gen.sh
```

也可以使用带确认环节的总脚本，一次完成上述流程：

```bash
./update_fwss_with_confirmation.py
```

它会先运行 `update_fwss_and_gen.sh`，再把最新无标签 CSV 与执行前的上一个 CSV 按 `name` 列比较，列出新增区县。此时可以手动修改 `add_labels/add_label_list.json`，完成后按回车继续；直接按回车表示无需修改，输入 `q` 并回车则中止最终生成。

第一个脚本会读取最新 FWSS、删除旧的 `loca` CSV，并生成无标签的 `经过县区名_base-WGS_path-WGS.csv`。第二个脚本会从当前 `loca` 文件名取得日期，生成 `add_label_list_fullname_YYYYMMDD.json`，再生成最终结果，并把带标签 CSV 备份到 `history/`。

如果 Python 不在默认环境中，可以通过 `PYTHON_BIN` 指定解释器，例如 `PYTHON_BIN=/path/to/python ./update_fwss_and_gen.sh`。

也可以手动执行底层命令：

```bash
python fwss_reader/fwss_reader.py
python gen_vis_keikenchi_map.py --date YYYYMMDD
python add_labels/resolve_full_names.py --date YYYYMMDD
python gen_vis_keikenchi_map.py --date YYYYMMDD
```

`gen_vis_keikenchi_map.py` 在找不到对应的 fullname 标签 JSON 时，会直接读取对应的 FWSS（有同日期 CSV 时优先读取 CSV），只生成初步的县区 CSV。标签解析完成后再次执行即可生成最终地图、统计和县区结果。

历史结果可在保留旧 `loca` CSV 时执行 `python gen_vis_keikenchi_map.py --history`，结果写入 `history/`。

# 参考
* Fog Machine：https://github.com/CaviarChen/fog-machine
* 中国大陆县区级行政区划：https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov
* 台湾行政区划：https://github.com/ronnywang/twgeojson
* 香港区议会分区：https://opendata.esrichina.hk/datasets/hong-kong-18-districts/
* 澳门堂区分区：https://github.com/ngsiolei/macau-map-data/tree/master/parishes
* 日本市区町村行政区划：https://gist.github.com/four4to6/769a1e2d77ef3f0aed019ef2434d101b
* 朝鲜行政区划：https://github.com/stiles/data/tree/master/north-korea-geography
* 韩国行政区划：https://github.com/southkorea/southkorea-maps/blob/master/kostat/2018/json/skorea-submunicipalities-2018-geo.json
* 越南行政区划：https://gisvn.com/ban-do-hanh-chinh-viet-nam
