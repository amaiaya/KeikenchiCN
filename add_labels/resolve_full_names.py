import json
import csv

CSV_FILE = "../经过县区名_base-GCJ_path-GCJ.csv"
JSON_FILE = "add_label_list.json"
OUTPUT_FILE = "add_label_list_fullname.json"

# Load all full names from CSV
full_names = []
with open(CSV_FILE, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        full_names.append(row["name"])

def find_matches(short_name):
    """Find all full names whose token suffix matches the short_name tokens."""
    short_tokens = short_name.split()
    n = len(short_tokens)
    return [fn for fn in full_names if fn.split()[-n:] == short_tokens]

with open(JSON_FILE, encoding="utf-8") as f:
    data = json.load(f)

all_unique = True
resolved = {}

for list_name, items in data.items():
    print(f"\n=== {list_name} ===")
    resolved[list_name] = []
    for item in items:
        matches = find_matches(item)
        if len(matches) == 0:
            print(f"  [未找到] {item}")
            all_unique = False
            resolved[list_name].append(item)
        elif len(matches) == 1:
            print(f"  {item} -> {matches[0]}")
            resolved[list_name].append(matches[0])
        else:
            print(f"  [多重匹配] {item}:")
            for m in matches:
                print(f"    - {m}")
            all_unique = False
            resolved[list_name].append(item)

resolved['stayed'] += [
    '西安市 长安区',
    '山东省 青岛市 市南区',
    '河南省 焦作市 修武县',
]

resolved['visited'] += [
    '辽宁省 大连市 旅顺口区',
    '辽宁省 大连市 沙河口区',
    '山东省 威海市 荣成市',
    '山东省 威海市 环翠区',
    '山东省 日照市 东港区',
    '山东省 青岛市 市南区',
    '山东省 青岛市 黄岛区',
    '山东省 济南市 莱芜区',
    '山东省 济南市 历下区',
    '山东省 泰安市 东平县',
    '江苏省 连云港市 海州区',
    '河北省 沧州市 吴桥县',
# 2018
    '甘肃省 张掖市 肃南裕固族自治县',
    '甘肃省 张掖市 临泽县',
    '青海省 西宁市 湟中区',
    '青海省 海南藏族自治州 共和县',
    '山东省 菏泽市 牡丹区',
    '山东省 枣庄市 台儿庄区',
    '山东省 潍坊市 奎文区'
]
resolved['alighted'] += [
    '辽宁省 大连市 甘井子区'
]
resolved['passed'] += [
    '山东省 青岛市 市北区',
    '山东省 青岛市 李沧区',
    '山东省 青岛市 胶州市',
    '山东省 青岛市 城阳区',
    '山东省 潍坊市 诸城市',
    '山东省 临沂市 沂水县',
    '山东省 淄博市 沂源县',
    '山东省 济南市 钢城区',
    '山东省 泰安市 岱岳区',
    '山东省 泰安市 肥城市',
# 去日照
    '山东省 泰安市 新泰市',
    '山东省 临沂市 沂南县',
    '山东省 日照市 莒县',
    '山东省 日照市 岚山区',
    '山东省 日照市 五莲县',
# 去连云港
    '山东省 临沂市 河东区',
    '山东省 临沂市 莒南县',
    '山东省 临沂市 临沭县',
    '江苏省 连云港市 赣榆区',
    '江苏省 连云港市 连云区',
# 去威海刘公岛
    '山东省 青岛市 即墨区',
    '山东省 烟台市 莱阳市',
    '山东省 烟台市 海阳市',
    '山东省 威海市 乳山市',
    '山东省 威海市 文登区',
# 去河北吴桥
    '山东省 济南市 市中区',
    '山东省 德州市 齐河县',
    '山东省 德州市 禹城市',
    '山东省 德州市 平原县',
    '山东省 德州市 陵城区',
    '山东省 德州市 德城区',
# 2018西北
    '青海省 西宁市 城中区',
    '青海省 西宁市 湟源县',
]

seen = set()
for list_name in list(data.keys()):
    new_list = []
    for v in resolved[list_name]:
        if v in seen:
            # skip duplicate in later list
            continue
        new_list.append(v)
        seen.add(v)
    resolved[list_name] = new_list

print()
if all_unique:
    print("所有元素均唯一匹配，正在保存全称 JSON...")
    for list_name in resolved:
        resolved[list_name] = sorted(resolved[list_name])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resolved, f, ensure_ascii=False, indent=4)
    print(f"已保存至 {OUTPUT_FILE}")
else:
    print("存在未匹配或多重匹配项，未保存新 JSON。请先解决上述问题。")